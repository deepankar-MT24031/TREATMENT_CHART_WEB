from flask import Flask, render_template, request, send_file, jsonify
import json
from datetime import datetime
import uuid
import os
import time
from json_generator import create_json_file
from pdf_generator import generate_picu_treatment_chart
from io import BytesIO
from reportlab.pdfgen import canvas
from database_handler import create_entry, return_database_with_history, search_entries, return_database_with_query_is_uuid  # Import the history function and search_entries

app = Flask(__name__)

# Assuming the create_json_file function is already imported
# from your_module import create_json_file


@app.route('/')
def index():
    try:
        # Load default format
        with open('RESOURCES/default_format.json', 'r') as f:
            default_data = json.load(f)
        
        # Get all JSON files in the RESOURCES directory
        json_files = []
        for file in os.listdir('RESOURCES'):
            if file.endswith('.json') and file != 'default_format.json':
                json_files.append(file)

        # Get database entries for search tab
        database_entries = return_database_with_history()

        return render_template('index.html', 
                             json_files=json_files,
                             default_data=default_data,
                             current_data=default_data,
                             database_entries=database_entries)  # Pass entries to template
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        return str(e), 500


@app.route('/download', methods=['POST'])
def download():
    try:
        # Get data from the form
        data = request.get_json()
        print("Received data:", data)  # Debug print

        # Validate required fields
        required_fields = {
            'Name': data.get('Name', '').strip(),
            'Age_year': data.get('Age_year', '').strip(),
            'Age_month': data.get('Age_month', '').strip(),
            'Sex': data.get('Sex', '').strip(),
            'uhid': data.get('uhid', '').strip(),
            'uuid': data.get('uuid', '').strip(),
            'bed_number': data.get('bed_number', '').strip()
        }

        # Check for missing or empty fields
        missing_fields = []
        for field, value in required_fields.items():
            if not value:
                # Convert field names to more readable format
                readable_field = field.replace('_', ' ').title()
                if field == 'uhid':
                    readable_field = 'UHID'
                missing_fields.append(readable_field)

        if missing_fields:
            error_message = f"Please fill in the following required fields: {', '.join(missing_fields)}"
            return jsonify({'error': error_message}), 400

        # If all required fields are present, proceed with the download
        val1 = {
            "Name": required_fields['Name'],
            "Age_year": required_fields['Age_year'],
            "Age_month": required_fields['Age_month'],
            "Sex": required_fields['Sex'],
            "uhid": required_fields['uhid'],
            "uuid": required_fields['uuid'],
            "bed_number": required_fields['bed_number'],
            "Diagnosis": data.get('Diagnosis', '').strip(),
            "Consultants": data.get('Consultants', '').strip(),
            "JR": data.get('JR', '').strip(),
            "SR": data.get('SR', '').strip()
        }

        # Get entries data from the form
        val2 = data.get('entries', {})

        # Get parameter values from the form data
        val3 = data.get('parameters', {})

        print("Processed data:", val1, val2, val3)  # Debug print

        # Call the create_json_file function
        format_type = "current"
        create_json_file(val1, val2, val3, format_type)

        # Sleep for 1 second to ensure the file is updated
        time.sleep(1)

        # Ensure the filename is correct with the .json extension
        filename = f'RESOURCES/{format_type}_format.json'

        # Read the created JSON file
        with open(filename, 'r') as file:
            json_data = json.load(file)
            print('JSON file loaded successfully')  # Debug print

        # Create database entry using your existing create_entry function
        create_entry(json_data)

        time.sleep(1)

        # Load settings from settings.json
        with open('settings.json', 'r') as f:
            settings_data = json.load(f)

        # Use heading, subheading, and font_size from settings
        heading = settings_data.get('heading', 'Treatment Chart')
        subheading = settings_data.get('subheading', 'Patient Information')
        font_size = settings_data.get('font_size', 10)

        # Call the generate_picu_treatment_chart function with the new arguments
        generate_picu_treatment_chart(heading, subheading, json_data, font_size=font_size)

        time.sleep(1)
        CURRENT_PDF = f'GENERATED_PDFS/current.pdf'

        # Check if the file exists before sending
        if not os.path.exists(filename):
            return jsonify({'error': 'Generated file not found'}), 404

        return send_file(
            CURRENT_PDF,
            as_attachment=True,
            download_name='current.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error in download route: {str(e)}")
        print(f"Error type: {type(e)}")  # Debug print
        import traceback
        print(f"Traceback: {traceback.format_exc()}")  # Debug print
        return jsonify({'error': str(e)}), 500


@app.route('/get_entries')
def get_entries():
    try:
        entries = return_database_with_history()
        return jsonify(entries)
    except Exception as e:
        print(f"Error getting entries: {str(e)}")
        return jsonify([]), 500


@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    name = data.get('name', '').strip()
    date = data.get('date', '').strip()
    uhid = data.get('uhid', '').strip()
    
    print(f"Search parameters - Name: '{name}', Date: '{date}', UHID: '{uhid}'")
    
    # Get all entries
    entries = return_database_with_history()
    print(f"Total entries found: {len(entries)}")
    
    # Filter entries based on search criteria
    filtered_entries = []
    for entry in entries:
        entry_name = str(entry[0]).lower() if entry[0] else ''
        entry_date = str(entry[1]) if entry[1] else ''
        entry_uhid = str(entry[2]) if entry[2] else ''
        
        name_match = not name or name.lower() in entry_name
        date_match = not date or date in entry_date
        uhid_match = not uhid or uhid in entry_uhid
        
        if name_match and date_match and uhid_match:
            filtered_entries.append(entry)
    
    print(f"Filtered entries found: {len(filtered_entries)}")
    return jsonify(filtered_entries)


@app.route('/get_entry/<uuid>')
def get_entry(uuid):
    try:
        print(f"Received request for UUID: {uuid}")  # Debug log
        
        # Get the entry from the database using return_database_with_query_is_uuid
        entry = return_database_with_query_is_uuid(param_uuid=uuid)
        print(f"Search result: {entry}")  # Debug log
        
        if not entry:
            print(f"No entry found for UUID: {uuid}")  # Debug log
            return jsonify({'error': 'Entry not found'}), 404
        
        print(f"Returning entry: {entry}")  # Debug log
        return jsonify(entry)
    except Exception as e:
        print(f"Error getting entry: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'GET':
        try:
            with open('settings.json', 'r') as f:
                settings_data = json.load(f)
            return jsonify(settings_data)
        except Exception as e:
            print(f"Error reading settings: {str(e)}")
            return jsonify({'error': str(e)}), 500
    elif request.method == 'POST':
        try:
            new_settings = request.get_json()
            with open('settings.json', 'w') as f:
                json.dump(new_settings, f, indent=2)
            return jsonify({'message': 'Settings updated successfully'})
        except Exception as e:
            print(f"Error updating settings: {str(e)}")
            return jsonify({'error': str(e)}), 500


@app.route('/ddi', methods=['POST'])
def ddi():
    try:
        data = request.get_json()
        # Simulate converting current JSON to a document
        # Return interactions with explicit severity labels
        results = {
            "table": [
                {"Drug 1": "Aspirin", "Drug 2": "Warfarin", "Interaction": "High"},
                {"Drug 1": "Lisinopril", "Drug 2": "Potassium", "Interaction": "Medium"},
                {"Drug 1": "Metformin", "Drug 2": "Contrast Dye", "Interaction": "Low"},
                {"Drug 1": "Unknown Drug", "Drug 2": "Unknown Drug", "Interaction": "Unknown"}
            ]
        }
        return jsonify(results)
    except Exception as e:
        print(f"Error in DDI route: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Ensure the folder exists
    if not os.path.exists('RESOURCES'):
        os.makedirs('RESOURCES')
    app.run(debug=True)
