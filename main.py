from flask import Flask, render_template, request, send_file
import json
from datetime import datetime
import uuid
import os
import time
from json_generator import create_json_file
from pdf_generator import generate_picu_treatment_chart
from io import BytesIO
from reportlab.pdfgen import canvas
app = Flask(__name__)

# Assuming the create_json_file function is already imported
# from your_module import create_json_file


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    # Get data from the form
    data = request.get_json()

    # Extract form fields
    val1 = {
        "name": data.get('name', 'Unknown'),
        "age_year": data.get('age_years', ''),
        "age_month": data.get('age_months', ''),
        "sex": data.get('sex', ''),
        "uhid": data.get('uuid', ''),
        "bed_number": data.get('bed', ''),
        "diagnosis": data.get('diagnosis', ''),
        "consultants": data.get('consultants', ''),
        "jr": data.get('jr', ''),
        "sr": data.get('sr', '')
    }

    # Dummy data for val2 (entries)
    val2 = {
        "entry_1": {
                "title": "Respiratory support",
                "subtitles": {"subtitle_1": {"content": "O2 via NC", "day": "D3", "dose": "2L", "volume": "N/A"}}
            },
        "entry_6": {"title": "Other Medications",
                    "subtitles": {"subtitle_3": {"content": "Med X", "day": "D3", "dose": "20mg", "volume": "3ml"}}}

    }

    # Dummy data for val3 (table rows)
    val3 = {
        "row_1": {"row_header_name": "Date", "row_header_description": "lol"},
            "row_2": {"row_header_name": "Weight", "row_header_description": "12 kg"}
    }

    # Call the create_json_file function
    format_type = "current"  # You can pass "default" or "current" as needed
    create_json_file(val1, val2, val3, format_type)

    # Sleep for 1 second to ensure the file is updated
    time.sleep(1)

    # Ensure the filename is correct with the .json extension
    filename = f'RESOURCES/{format_type}_format.json'

    with open(filename, 'r') as file:
        json_data = json.load(file)
        print('loaded')
    time.sleep(1)

    generate_picu_treatment_chart('destroy', 'WORLD', json_data, font_size=10)  # Example font size
    time.sleep(1)
    CURRENT_PDF = f'GENERATED_PDFS/current.pdf'

    # Check if the file exists before sending
    if not os.path.exists(filename):
        return "File not found", 404

    # Return the JSON file as a download with the correct extension
    # return send_file(filename, as_attachment=True, mimetype='application/json')

    # buffer = BytesIO()
    # c = canvas.Canvas(buffer)
    # c.showPage()  # Add a blank page
    # c.save()
    # buffer.seek(0)
    #
    return send_file(
        CURRENT_PDF,
        as_attachment=True,
        download_name='current.pdf',
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    # Ensure the folder exists
    if not os.path.exists('RESOURCES'):
        os.makedirs('RESOURCES')
    app.run(debug=True)
