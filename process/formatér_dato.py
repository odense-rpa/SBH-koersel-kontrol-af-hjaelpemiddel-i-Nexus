from datetime import datetime


def format_date(date_string):
    if not date_string:
        return ""
    try:
        # Parse ISO format (e.g., "2025-08-15T14:00:05") and format to dd-mm-yyyy
        date_obj = datetime.fromisoformat(
            date_string.replace("Z", "+00:00")
        )
        return date_obj.strftime("%d-%m-%Y")
    except (ValueError, AttributeError):
        return date_string  # Return original if parsing fails
