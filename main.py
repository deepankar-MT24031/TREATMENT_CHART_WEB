from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
import json
from datetime import datetime, timedelta
import uuid
import os
import time
from json_generator import create_json_file
from pdf_generator import generate_picu_treatment_chart
from io import BytesIO
from reportlab.pdfgen import canvas
from database_handler import create_entry, return_database_with_history, search_entries, return_database_with_query_is_uuid  # Import the history function and search_entries
import requests
import shutil

app = Flask(__name__, static_folder='RESOURCES', static_url_path='/resources')

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


def cleanup_old_pdfs(max_age_days=7, max_files=100):
    """
    Clean up old PDF files to prevent storage overflow.
    Args:
        max_age_days: Maximum age of PDFs to keep (default: 7 days)
        max_files: Maximum number of PDFs to keep (default: 100)
    """
    try:
        pdf_dir = 'GENERATED_PDFS'
        if not os.path.exists(pdf_dir):
            return

        # Get all PDF files
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        
        # Sort files by modification time (oldest first)
        pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join(pdf_dir, x)))
        
        # Calculate cutoff time
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        # Remove files older than max_age_days
        for pdf_file in pdf_files:
            file_path = os.path.join(pdf_dir, pdf_file)
            if os.path.getmtime(file_path) < cutoff_time:
                os.remove(file_path)
                print(f"Removed old PDF: {pdf_file}")
        
        # If still too many files, remove oldest ones
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        if len(pdf_files) > max_files:
            for pdf_file in pdf_files[:-max_files]:
                file_path = os.path.join(pdf_dir, pdf_file)
                os.remove(file_path)
                print(f"Removed excess PDF: {pdf_file}")
                
    except Exception as e:
        print(f"Error in cleanup_old_pdfs: {str(e)}")


@app.route('/download', methods=['POST'])
def download():
    try:
        # Clean up old PDFs before generating new one
        cleanup_old_pdfs()
        
        # Get the JSON data from the request
        json_data = request.get_json()
        
        # Generate timestamp for unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Ensure GENERATED_PDFS directory exists
        os.makedirs('GENERATED_PDFS', exist_ok=True)
        
        # Create a unique filename using patient name, UHID, and timestamp
        name = json_data.get("Name", "UnknownName").replace(" ", "_")
        uhid = json_data.get("uhid", "NoUHID").replace(" ", "_")
        filename = os.path.join('GENERATED_PDFS', f'{name}_{uhid}_{timestamp}.pdf')
        CURRENT_PDF = filename

        # Get settings from settings.json
        with open('settings.json', 'r') as f:
            settings_data = json.load(f)

        # Extract settings
        heading = settings_data.get('heading', '')
        subheading = settings_data.get('subheading', '')
        font_size = settings_data.get('font_size', 13)

        # Call the generate_picu_treatment_chart function with the new arguments
        generate_picu_treatment_chart(heading, subheading, json_data, font_size=font_size)

        time.sleep(1)

        # Check if the file exists before sending
        if not os.path.exists(filename):
            return jsonify({'error': 'Generated file not found'}), 404

        return send_file(
            filename,
            as_attachment=True,
            download_name=f'{name}_{uhid}_{timestamp}.pdf',
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
            # Convert the logo path to a URL path
            if 'logo_upload' in settings_data and 'path' in settings_data['logo_upload']:
                logo_path = settings_data['logo_upload']['path']
                # Convert the file path to a URL path
                logo_filename = os.path.basename(logo_path)
                settings_data['logo_upload']['url'] = f'/resources/{logo_filename}'
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


@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename.lower().endswith('.png'):
            # Save the file as website_logo.png
            file.save('RESOURCES/website_logo.png')
            
            # Update settings.json with the new logo path
            with open('settings.json', 'r') as f:
                settings_data = json.load(f)
            
            settings_data['logo_upload'] = {
                'path': 'RESOURCES/website_logo.png',
                'url': '/resources/website_logo.png'
            }
            
            with open('settings.json', 'w') as f:
                json.dump(settings_data, f, indent=2)
            
            return jsonify({'message': 'Logo uploaded successfully'})
        else:
            return jsonify({'error': 'Only PNG files are allowed'}), 400
            
    except Exception as e:
        print(f"Error uploading logo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/ddi', methods=['POST'])
def ddi():
    try:
        # Get the JSON data from the request
        json_data = request.get_json()
        
        # Save the current data to current_format.json
        with open('RESOURCES/current_format.json', 'w') as f:
            json.dump(json_data, f, indent=2)
        
        # Wait for file to be written
        time.sleep(1)
        
        # Use our fetch_ddi_data function
        from ddiwindowmodified import fetch_ddi_data
        try:
            results = fetch_ddi_data(json_data)
            if not results or 'table' not in results:
                return jsonify({'error': 'No results returned from DDI server'}), 503
            return jsonify(results)
        except ConnectionRefusedError as e:
            return jsonify({'error': str(e)}), 503
        except ValueError as e:
            return jsonify({'error': str(e)}), 503
        except ConnectionError as e:
            return jsonify({'error': str(e)}), 503
        except requests.exceptions.RequestException as e:
            if 'No host supplied' in str(e):
                return jsonify({'error': 'IP address is missing. Please check your IP settings in the Settings menu.'}), 503
            elif 'Failed to connect' in str(e):
                return jsonify({'error': 'Failed to connect to DDI server. Please check your IP and Port settings.'}), 503
            else:
                return jsonify({'error': f'Connection error: {str(e)}'}), 503
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"Error in DDI route: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/resources/<path:filename>')
def serve_resource(filename):
    return send_from_directory('RESOURCES', filename)


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host=host, port=port, debug=False)
