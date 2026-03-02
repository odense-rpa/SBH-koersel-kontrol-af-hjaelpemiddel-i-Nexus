import asyncio
import logging
import sys
from datetime import datetime
from kmd_nexus_client.manager import NexusClientManager
from kmd_nexus_client.tree_helpers import (
    filter_by_predicate,
)
from process.hjælpemidler import GODKENDTE_HJÆLPEMIDLER_I_NEXUS
from process.formatér_dato import format_date
from process.xflow import afsend_til_xflow
from odk_tools.tracking import Tracker
from xflow_client import XFlowClient, ProcessClient
from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)

nexus: NexusClientManager
xflow_client: XFlowClient
xflow_process_client: ProcessClient

tracker: Tracker

proces_navn = "SBH kørsel - Kontrol af hjælpemiddel i Nexus"


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    xlow_søge_query = {
        "text": "",
        "processTemplateIds": ["753"],
        "startIndex": 0,
        "createdDateFrom": "01-01-1980",
        "createdDateTo": datetime.today().strftime("%d-%m-%Y"),
    }

    igangværende_processer = xflow_process_client.search_processes_by_current_activity(
        query=xlow_søge_query,
        activity_name="RPAIntegration",
    )

    for proces in igangværende_processer:
        blanketter = proces["blanketter"]

        samlet_ansøgning = filter_by_predicate(
            roots=blanketter, predicate=lambda x: x["blanketnavn"] == "SBH - Samlet"
        )
        cpr_nummer_predicate = filter_by_predicate(
            roots=samlet_ansøgning[0]["elementer"],
            predicate=lambda x: (
                x["identifier"] in ("Ansøger-AnsøgerSelv", "Ansøger-AnsøgerPåVegneAf")
            ),
        )
        # find cpr-nummer på ansøger:
        cpr_nummer = (
            cpr_nummer_predicate[0].get("values", {}).get("CprNummer")
            if cpr_nummer_predicate
            else None
        )
        if not cpr_nummer:
            logger.warning(
                f"Proces {proces['publicId']} har ikke et gyldigt CPR-nummer. Springes over."
            )
            continue
        # tilføj data til queue:
        data = {
            "procesid": proces["publicId"],
            "cprnummer": cpr_nummer,
        }
        workqueue.add_item(data, reference=cpr_nummer)


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict

            try:
                # hent borger i nexus via cpr-nummer
                borger = nexus.borgere.hent_borger(data["cprnummer"])
                if borger is None:
                    # borger ikke fundet i nexus - skal bare returnere en blanket med "BORGER IKKE FUNDET I NEXUS" i de relevante felter og så avancere processen:
                    afsend_til_xflow(
                        xflow_process_client,
                        data["procesid"],
                        "BORGER IKKE FUNDET I NEXUS",
                        "BORGER IKKE FUNDET I NEXUS",
                    )
                    continue

                borgers_udlån = nexus.borgere.hent_udlån(borger)
                # check om GODKENDTE_HJÆLPEMIDLER_I_NEXUS er i borgers_udlån i ["item"]["product"]["categoryName"]:
                borgers_godkendte_udlån = [
                    udlån
                    for udlån in borgers_udlån
                    if any(
                        hjælpemiddel.lower()
                        in udlån.get("item", {})
                        .get("product", {})
                        .get("categoryName", "")
                        .lower()
                        for hjælpemiddel in GODKENDTE_HJÆLPEMIDLER_I_NEXUS
                    )
                ]

                # lav en liste med borgers_godkendte_udlån hvor hvert item indeholder categoryName, orderedDate og firstDeliveredDate:
                borgers_godkendte_udlån_info = [
                    {
                        "ISO navn": udlån.get("item", {})
                        .get("product", {})
                        .get("categoryName", ""),
                        "Ordredato": format_date(udlån.get("orderedDate", "")),
                        "Udlånsdato": format_date(udlån.get("firstDeliveredDate", "")),
                        "Paragraf": udlån.get("grant", {}).get("paragraph", ""),
                    }
                    for udlån in borgers_godkendte_udlån
                ]

                # Convert to formatted text with html tags:
                if borgers_godkendte_udlån_info:
                    udlån_text = "Godkendte hjælpemidler fundet i Nexus:<br><br>"
                    udlån_items = []
                    for i, udlån in enumerate(borgers_godkendte_udlån_info, 1):
                        item_text = f"{i}. {udlån['ISO navn']}<br>   Ordredato: {udlån['Ordredato']}<br>   Udlånsdato: {udlån['Udlånsdato']}<br>   Paragraf: {udlån['Paragraf']}<br><br>"
                        udlån_items.append(item_text)
                    udlån_text += "".join(udlån_items)
                else:
                    udlån_text = "Ingen godkendte hjælpemidler fundet i Nexus."

                # finder borgers "samlet faglig vurdering" skemaer i nexus
                borger_skemaer = nexus.skemaer.hent_skemareferencer(borger)
                samlet_faglig_vurdering_referencer = [
                    skema
                    for skema in borger_skemaer
                    if skema.get("Navn") == "Samlet faglig vurdering"
                ]

                # variable til at samle alle godkendte skemaer
                godkendte_skemaer = []

                # kigger alle samlet faglig vurdering skemaer igennem for at se om der er et godkendt hjælpemiddel:
                for skema in samlet_faglig_vurdering_referencer:
                    skema_detaljer = nexus.skemaer.hent_skema_fra_reference(skema)
                    # check om ["items"][0]["value"] fremkommer i GODKENDTE_HJÆLPEMIDLER_I_NEXUS:
                    if (
                        skema_detaljer
                        and "items" in skema_detaljer
                        and len(skema_detaljer["items"]) > 0
                    ):
                        skema_overskrift_værdi = skema_detaljer["items"][0].get(
                            "value", ""
                        )
                        # hent introduktion/sammenfatning samt konklusion/afgørelse og sæt godkendte_skema til True
                        if any(
                            hjælpemiddel.lower() in skema_overskrift_værdi.lower()
                            for hjælpemiddel in GODKENDTE_HJÆLPEMIDLER_I_NEXUS
                        ):
                            introduktion_sammenfatning_værdi = skema_detaljer["items"][
                                1
                            ].get("value", "")
                            konklusion_afgørelse_værdi = skema_detaljer["items"][3].get(
                                "value", ""
                            )
                            skema_created_date = skema_detaljer.get("createDate", "")

                            # tilføj til listen af godkendte skemaer
                            godkendte_skemaer.append(
                                {
                                    "Oprettet": format_date(skema_created_date),
                                    "Overskrift": skema_overskrift_værdi,
                                    "Introduktion": introduktion_sammenfatning_værdi,
                                    "Konklusion": konklusion_afgørelse_værdi,
                                }
                            )

                # format alle godkendte skemaer til tekst
                if godkendte_skemaer:
                    skema_text = "Godkendte skemaer fundet i Nexus:\n\n"
                    for i, skema in enumerate(godkendte_skemaer, 1):
                        skema_text += f"{i}. Samlet faglig vurdering (Oprettet: {skema['Oprettet']})\n"
                        skema_text += f"   <b>Overskrift:</b> {skema['Overskrift']}\n"
                        skema_text += f"   <b>Introduktion/Sammenfatning:</b> {skema['Introduktion']}\n"
                        skema_text += (
                            f"   <b>Konklusion/Afgørelse:</b> {skema['Konklusion']}\n\n"
                        )
                else:
                    skema_text = "Ingen godkendte skemaer fundet."

                # blanket data, der skal sendes tilbage til xflow:
                afsend_til_xflow(xflow_process_client, data["procesid"], udlån_text, skema_text)
                
                # Afregn
                tracker.track_task(process_name=proces_navn)

            except Exception as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()

    # Initialize external systems for automation here..
    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    xflow_credential = Credential.get_credential("Xflow - produktion")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    nexus = NexusClientManager(
        client_id=nexus_credential.username,
        client_secret=nexus_credential.password,
        instance=nexus_credential.data["instance"],
    )

    xflow_client = XFlowClient(
        token=xflow_credential.password,
        instance=xflow_credential.data["instance"],
    )
    xflow_process_client = ProcessClient(xflow_client)

    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
