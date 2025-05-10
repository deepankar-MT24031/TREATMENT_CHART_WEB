import json
from datetime import datetime
import uuid


def create_json_file(val1,val2,val3,format ):
    """
    Create a JSON file with the specified data.

    Parameters:
        file_name (str): The name of the JSON file to be created.
        data (dict): The data to be written to the JSON file.


    """


    default_format = {
        "uuid": f"{uuid.uuid4()}",
        "date": f"{datetime.today().strftime('%Y-%m-%d')}",
        "default_Bed_count": 16,
        "default_Sex_count": 3,
        "default_Entries_count": 5,
        "default_table_rows_count": 5,

        "Name": "",
        "Age_year": "",
        "Age_month": "",
        "Sex":"",
        "uhid":" ",
        "bed_number": "1",
        "Diagnosis": "",
        "Consultants": "",
        "JR": "",
        "SR": "",

        "each_sex_value_names": {"Sex_1_name": "Male", "Sex_2_name": "Female", "Sex_3_name": "Other"},

        "each_entry_layout": {
            "entry_1": {"title": "Antimicrobials", "title_Description": "Some_details_about_antimicrobials"},
            "entry_2": {"title": "Feeds", "title_Description": "Some_details_about_feeds"},
        },

        "each_table_row_layout": {

            "row_1": {"row_header_name": "Date", "row_header_description": "some_date"},
            "row_2": {"row_header_name": "Time", "row_header_description": "some_time"},
            "row_3": {"row_header_name": "Weight", "row_header_description": "some_weight"},
            "row4": {"row_header_name": "Height", "row_header_description": "some_Height"},
            "row5": {"row_header_name": "IVF", "row_header_description": "some_IVF"},

        },

    }

    # Create a new dictionary for the desired format
    each_table_row_layout = {}

    # Iterate over the original dictionary
    for index, (key, value) in enumerate(val3.items(), start=1):
        # Create row number based on the index
        row_key = f"row_{index}"
        # Add to the new dictionary
        each_table_row_layout[row_key] = {
            "row_header_name": value["row_header_name"],
            "row_header_description": value["row_header_description"]
        }

    # Create a new dictionary for the desired format
    each_entry_layout = val2

    # # Iterate through the original dictionary
    # for index, (key, value) in enumerate(val2.items(), start=1):
    #     # Generate the entry key (entry_1, entry_2, ...)
    #     entry_key = f"entry_{index}"
    #
    #     # Extract title and title_Description from the value list
    #     title = value[0]
    #     title_description = value[1]
    #
    #     # Add to the new dictionary
    #     each_entry_layout[entry_key] = {
    #         "title": title,
    #         "title_Description": title_description
    #     }

    current_format = {
        "uuid": f"{uuid.uuid4()}",
        "datetime": f"{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}",
        "date": f"{datetime.today().strftime('%d-%m-%Y')}",
        "default_Bed_count": 16,
        "default_Sex_count": 3,
        "default_Entries_count": 5,
        "default_table_rows_count": 5,
        "each_sex_value_names": {"Sex_1_name": "Male", "Sex_2_name": "Female", "Sex_3_name": "Other"},
        "Name": val1["Name"],
        "Age_year": val1["Age_year"],
        "Age_month": val1["Age_month"],
        "Sex": val1["Sex"],
        "uhid": val1["uhid"],
        "bed_number": val1["bed_number"],
        "Diagnosis": val1.get("Diagnosis", ""),
        "Consultants": val1.get("Consultants", ""),
        "JR": val1.get("JR", ""),
        "SR": val1.get("SR", ""),
        "each_entry_layout": each_entry_layout,
        "each_table_row_layout": each_table_row_layout
    }

    if format=="default":
        data = default_format

    if format=="current":
        data = current_format

    try:
        with open(f'RESOURCES/{format}_format.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)
        print(f"JSON file '{format}_format.json' has been created successfully.")
    except Exception as e:
        print(f"An error occurred while creating the JSON file: {e}")



# Example usage

