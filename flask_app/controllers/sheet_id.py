import smartsheet
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


def find_column_id_by_name(sheet_id, column_name):
    try:
        smartsheet_token = os.getenv('SMARTSHEET_API_TOKEN')
        if not smartsheet_token:
            raise ValueError("Missing Smartsheet API token")

        smartsheet_client = smartsheet.Smartsheet(smartsheet_token)

        response = smartsheet_client.Sheets.get_sheet(sheet_id)
        if response.request_response.status_code != 200:
            print("Failed to fetch sheet:", response.message)
            return None

        for column in response.columns:
            if column.title == column_name:
                return column.id
    except smartsheet.exceptions.ApiError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

    return None


sheet_id = 1954899010316164  # Replace with your actual sheet ID
column_name = 'Submittal Status'  # Replace with your actual column name
column_id = find_column_id_by_name(sheet_id, column_name)

if column_id:
    print(f"The column ID for '{column_name}' is: {column_id}")
else:
    print("Column ID not found")
