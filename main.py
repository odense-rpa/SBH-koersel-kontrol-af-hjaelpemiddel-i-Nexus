import asyncio
import logging
import sys
from datetime import datetime

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
            "742"
        ],
        "startIndex": 0,        
        "createdDateFrom": "01-01-1980",
        "createdDateTo":  datetime.today().strftime('%d-%m-%Y'),
    }

    igangværende_processer = xflow_process_client.search_processes_by_current_activity(
        query=xlow_søge_query,
        activity_name="Start"
    )
    print("hej")

    for proces in igangværende_processer:
        print(proces)

        ønsket_hjælpemiddel = str(xflow_process_client.find_process_element_value(proces, "test", "test2"))




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
