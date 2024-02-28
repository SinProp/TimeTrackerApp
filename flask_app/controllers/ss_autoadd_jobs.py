import smartsheet
import json
from ..config.config import (
    SMARTSHEET_API_KEY, SHEET_ID, SUBMITTAL_STATUS_COLUMN_ID, IM_NUMBER_COLUMN_ID, SCOPE_COLUMN_ID, GC_COLUMN_ID)

smartsheet_client = smartsheet.Smartsheet(SMARTSHEET_API_KEY)


def fetch_detailed_row_data():
    sheet = smartsheet_client.Sheets.get_sheet(SHEET_ID)
    detailed_row_data = []

    for row in sheet.rows:
        # Create a dictionary to hold the cell data
        row_data = {
            'row_id': row.id
        }

        # Fetch each cell by column ID

        for cell in row.cells:
            if str(cell.column_id) == SUBMITTAL_STATUS_COLUMN_ID:
                row_data['submittal_status'] = cell.value
            elif str(cell.column_id) == IM_NUMBER_COLUMN_ID:
                row_data['im_number'] = cell.value
            elif str(cell.column_id) == GC_COLUMN_ID:
                row_data['gc'] = cell.value
            elif str(cell.column_id) == SCOPE_COLUMN_ID:
                row_data['scope'] = cell.value

        # Only add rows that have a Submittal Status
        if 'submittal_status' in row_data:
            detailed_row_data.append(row_data)

    return detailed_row_data


if __name__ == "__main__":
    detailed_values = fetch_detailed_row_data()
    print(json.dumps(detailed_values, indent=4))
