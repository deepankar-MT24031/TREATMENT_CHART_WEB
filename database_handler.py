from tinydb import Query
from tinydb import TinyDB
import os
from datetime import datetime

def catch_exceptions(handler=None):
    """
    Decorator to catch exceptions in the decorated function.
    :param handler: Optional function to handle the exception.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # print(args,kwargs)
            try:
                # print(f" [======]in {func.__name__}:")
                return func(*args, **kwargs)
            except Exception as e:
                if handler:
                    # Call the custom handler if provided
                    handler(e)
                else:
                    # Default behavior: Print the exception
                    print(args, kwargs)
                    print(f"An error occurred in {func.__name__}: {e}")

        return wrapper
    return decorator

# Ensure DATABASE directory exists
if not os.path.exists('DATABASE'):
    os.makedirs('DATABASE')

# Initialize TinyDB
db = TinyDB('DATABASE/db.json')

# Find all records
all_users = db.all()
# print("All Users:", all_users)
# for user in all_users:
#     print(user)

## Create a query
q = Query()


# def return_database_sorted_according_to_date():
#
#     # Sort entries by date in ascending order
#     sorted_entries = sorted(
#         db.all(),
#         key=lambda x: datetime.strptime(x.get('date', '1970-01-01'), '%Y-%m-%d')
#     )
#     for entries in sorted_entries:
#         print(entries["Name"], entries["uhid"], entries["date"])

def return_database_with_history():
    # Sort entries by date in ascending order
    to_return_nested_list_for_history = []
    sorted_entries = sorted(
        db.all(),
        key=lambda x: datetime.strptime(x.get('datetime', '01-01-1970T00:00:00'), '%d-%m-%Y %H:%M:%S',)
    )
    if sorted_entries != None:
        # Take only the last 100 entries after sorting
        for entries in reversed(sorted_entries[-2:]):
            to_return_nested_list_for_history.append([entries["Name"], entries["datetime"], entries["uhid"], entries["uuid"]])
    return to_return_nested_list_for_history

def return_database_with_query_is_uuid(param_uuid="NA"):
    db = TinyDB('DATABASE/db.json')
    # print("all fione here")
    if param_uuid != "NA":
        # Sort entries by date in ascending order
        to_return_single_dict = {}

        # UUID to search for
        search_uuid = param_uuid

        Record = Query()

        # Search the database
        to_return_single_dict_but_its_list_now  = db.search(Record.uuid == search_uuid)

        if to_return_single_dict_but_its_list_now:
            print("databasehandler.py->>>>Entry found:", to_return_single_dict_but_its_list_now )
            print("databasehandler.py->>>>typeof returning_dict:", type(to_return_single_dict_but_its_list_now ))
            # Convert to dictionary
            to_return_single_dict = to_return_single_dict_but_its_list_now[0] if to_return_single_dict_but_its_list_now else {}
            return to_return_single_dict
        else:
            print("databasehandler.py->>>>No entry found with that UUID.")
            return None
    return None

@catch_exceptions()
def return_databse_with_query_is_name_and_date_and_uhid(param_name=None,param_date=None,param_uhid=None):

    db = TinyDB('DATABASE/db.json')

    if param_name=="" and param_date=="" and param_uhid=="":
        print("please enter any one field to begin search")
    else:
        print("kuch to mila")
        # Define the fields to query (set some fields as None if not querying them)
        if param_name != None:
            name_to_find = param_name.lower() if len(param_name)>0 else None
        else:
            name_to_find = None

        if param_date != None:
            date_to_find = param_date if len(param_date)==10 else None

        else:
            date_to_find = None
            # Set None if not querying this field
        if param_uhid != None:
            uhid_to_find = param_uhid if len(param_uhid)==9 else None
        else:
            uhid_to_find = None
        # uhid_to_find = None
        print(name_to_find,date_to_find,uhid_to_find)
        print(param_name,param_date,param_uhid)

        # Use the Query object to construct the query
        Entry = Query()

        # Start with an empty query
        query = None

        # Dynamically build the query based on provided fields
        if name_to_find:
            query = (Entry.Name.test(lambda x: name_to_find.lower() in x.lower())) if query is None else query & (Entry.Name == name_to_find)
        if date_to_find:
            query = (Entry.date == date_to_find) if query is None else query & (Entry.date == date_to_find)

        if uhid_to_find:
            query = (Entry.uhid == uhid_to_find) if query is None else query & (Entry.uhid == uhid_to_find)

        # Perform the query if a condition exists
        if query:
            result = db.search(query)
            print("Matching entries:", len(result))
            print("after search---------::::")
            sorted_entries_by_datetime = sorted(
                result,
                key=lambda x: datetime.strptime(x.get('datetime', '01-01-1970T00:00:00'), '%d-%m-%Y %H:%M:%S', )
            )
            for i in result:
                print(i)

            to_return_nested_list_for_search= []
            for entries_search in reversed(sorted_entries_by_datetime):
                # print(entries["Name"], entries["date"],entries["uhid"],entries["uuid"])
                to_return_nested_list_for_search.append([entries_search["Name"], entries_search["datetime"], entries_search["uhid"], entries_search["uuid"]])
            return  to_return_nested_list_for_search
        else:
            print("No query conditions provided.")
            return -1




# return_database_with_query_is_uuid(param_uuid="1911428e-b7e5-4f2f-80a8-9be47e5219a9")

def create_entry(json_data):
    """
    Create a new entry in the database with the provided JSON data.
    Adds timestamp and ensures required fields are present.
    """
    try:
        # Add timestamp if not present
        if 'datetime' not in json_data:
            json_data['datetime'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        
        # Ensure required fields are present
        required_fields = ['Name', 'uhid', 'bed_number']
        for field in required_fields:
            if field not in json_data:
                json_data[field] = ''

        # Ensure optional fields are present
        optional_fields = ['Consultants', 'JR', 'SR', 'Diagnosis']
        for field in optional_fields:
            if field not in json_data:
                json_data[field] = ''

        # Insert the data into the database
        db.insert(json_data)
        print(f"Successfully created database entry for {json_data.get('Name', 'Unknown')}")
        return True
    except Exception as e:
        print(f"Error creating database entry: {str(e)}")
        return False

def search_entries(name=None, date=None, uuid=None):
    """
    Search for entries in the database based on provided criteria.
    Returns all matching entries.
    """
    try:
        Entry = Query()
        query = None

        # Build query based on provided parameters
        if name:
            query = Entry.Name.search(name)
        if date:
            query = (query & Entry.datetime.search(date)) if query else Entry.datetime.search(date)
        if uuid:
            query = (query & Entry.uhid.search(uuid)) if query else Entry.uhid.search(uuid)

        # If no search criteria provided, return all entries
        if not query:
            return db.all()

        # Return matching entries
        return db.search(query)
    except Exception as e:
        print(f"Error searching database: {str(e)}")
        return []

def get_all_entries():
    """
    Get all entries from the database.
    """
    try:
        return db.all()
    except Exception as e:
        print(f"Error getting all entries: {str(e)}")
        return []





