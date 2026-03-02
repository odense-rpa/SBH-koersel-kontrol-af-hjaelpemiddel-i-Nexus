from datetime import datetime


def afsend_til_xflow(xflow_process_client, procesid: str, udlån_text: str, skema_text: str):
    blanket_data = {
        "formValues": [
            {
                "elementIdentifier": "RPASignatur",
                "valueIdentifier": "Tekst",
                "value": "Behandlet af Tyra (RPA)",
            },
            {
                "elementIdentifier": "RPABehandletDato",
                "valueIdentifier": "Dato",
                "value": datetime.today().strftime("%d-%m-%Y"),
            },
            {
                "elementIdentifier": "InformationFraNEXUS-udlån",
                "valueIdentifier": "Tekst",
                "value": udlån_text,
            },
            {
                "elementIdentifier": "InformationFraNEXUS-skema",
                "valueIdentifier": "Tekst",
                "value": skema_text,
            },
        ]
    }
    xflow_process_client.update_process(procesid, blanket_data)
    xflow_process_client.advance_process(procesid)
