import smartsheet

# Authenticate with the Smartsheet API
smartsheet_client = smartsheet.Smartsheet(
    'c5MqhSkXLnRDk8s7rtYYlr4nhcwvjXXRCV1lj')

# ID of the Smartsheet
sheet_id = 1954899010316164

# Get the sheet details
sheet = smartsheet_client.Sheets.get_sheet(sheet_id)

# Print each column's name and ID
for column in sheet.columns:
    print(f"Column Name: {column.title}, Column ID: {column.id}")
