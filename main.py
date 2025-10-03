import asyncio
import logging
import sys
from datetime import datetime
from kmd_nexus_client.tree_helpers import (
    filter_by_predicate,    
)


from odk_tools.tracking import Tracker

from xflow_client import XFlowClient, ProcessClient
from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)


xflow_client: XFlowClient
xflow_process_client: ProcessClient

tracker: Tracker

proces_navn = "SBH kørsel - Kontrol af hjælpemiddel i Nexus"

async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    xlow_søge_query = {
        "text": "",
        "processTemplateIds": [
            "743"
        ],
        "startIndex": 0,        
        "createdDateFrom": "01-01-1980",
        "createdDateTo":  datetime.today().strftime('%d-%m-%Y'),
    }

    igangværende_processer = xflow_process_client.search_processes_by_current_activity(
        query=xlow_søge_query,
        activity_name="RPAIntegration",
    )
    print("hej")

    for proces in igangværende_processer:

        blanketter = proces["blanketter"]

        samlet_ansøgning = filter_by_predicate(
            roots=blanketter,
            predicate=lambda x: x["blanketnavn"] == "Christian tester"
        )
        filtreret_ansøgning = xflow_client.traverse_json_for_referable_elements(samlet_ansøgning[0])
        hjælpemiddel_predicate = filter_by_predicate(
            roots=filtreret_ansøgning,
            predicate=lambda x: x["identifier"] == "ElementMultiSelectHjælpemiddel"
        )
        # find værdier hjælpemiddel_predicate[0]["values"]["MultiSelectTekst"] og tilføj dem til en liste:
        hjælpemiddel_værdi = hjælpemiddel_predicate[0]["values"]["MultiSelectTekst"]
        
        # check om der er ansøgt om "Andet" og hent værdien
        findes_andet_hjælpemiddel = "Andet" in hjælpemiddel_værdi
        if findes_andet_hjælpemiddel:
            andet_hjælpemiddel_værdi = hjælpemiddel_predicate[0]["children"][0]["values"].get("Tekst", "")

        # split hjælpemiddel_værdi ved komma og fjern evt. mellemrum
        if isinstance(hjælpemiddel_værdi, list):
            # If it's already a list, flatten it and split each item
            hjælpemiddel_værdi_liste = []
            for item in hjælpemiddel_værdi:
                hjælpemiddel_værdi_liste.extend([x.strip() for x in item.split(",")])
        else:
            # If it's a string, split it directly
            hjælpemiddel_værdi_liste = [x.strip() for x in hjælpemiddel_værdi.split(",")]
        print("hej")


            # andet_predicate = filter_by_predicate(
            #     roots=hjælpemiddel_predicate,
            #     predicate=lambda x: x["identifier"] == "ElementTextfield"
            # )

            # if(hjælpemiddel_predicate and len(hjælpemiddel_predicate) > 0):
            # hjælpemiddel_værdi = 




    print("stop")



async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
 
            try:
                # Process the item here
                pass
            except WorkItemError as e:
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

    xflow_client = XFlowClient(
        token=xflow_credential.password,
        instance=xflow_credential.data["instance"],
    )
    xflow_process_client = ProcessClient(xflow_client)

    tracker = Tracker(
        username=tracking_credential.username,
        password=tracking_credential.password
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
