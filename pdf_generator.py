import os
import subprocess
import json
import time
import sys
# --- Keep other imports ---
import tempfile # Added for temporary directory
import shutil   # Added for moving files
import re
from datetime import datetime


def split_string(s,length=10):
    if len(s) > length:
        return '\n'.join(s[i:i+length] for i in range(0, len(s), length))
    return s

# Replace your escape_latex function with this version


# @catch_exceptions() # Assuming decorator is defined elsewhere
def escape_latex(s):
    if not isinstance(s, str) or not s.strip():
        return "" # Return empty string for None, empty, or whitespace-only
    if s is None:
        return ""

    s = s.strip() # Strip whitespace first
    if not s:
        return ""

    # 1. Escape literal backslash FIRST to avoid interfering with other escapes
    # This assumes backslashes in the input JSON are meant to be literal characters
    temp_s = s.replace("\\", r"\textbackslash{}")

    # 2. Define other replacements (excluding backslash now)
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",  # Correct underscore escape
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        # Generally avoid escaping {}[]() unless they cause specific issues
        "\"": r"''", # Double quotes -> two single quotes
        "'": r"'",  # Keep single quote as is (or use ` for left, ' for right if needed)
        "\n": r" \\ ",  # Preserve line breaks as LaTeX line breaks
    }

    # 3. Apply the rest of the replacements
    for char, escape in replacements.items():
        # Make sure we don't re-process parts of already inserted escapes
        # (This simple replace loop can have issues with overlapping patterns,
        # but let's try it first)
        temp_s = temp_s.replace(char, escape)

    return temp_s

# --- Assume PyQt5 imports and other helper functions like catch_exceptions, escape_latex, etc. are defined above ---

# Ensure sanitize_filename is defined (used by the caller)
# Make sure sanitize_filename is defined and available
def sanitize_filename(filename):
    """Removes or replaces invalid characters commonly problematic in filenames."""
    # Ensure input is a string
    if not isinstance(filename, str):
        filename = str(filename) # Convert if not already a string

    # Remove leading/trailing whitespace
    filename = filename.strip()

    # Replace invalid characters with '_'
    # Invalid chars for Windows: < > : " / \ | ? *
    # Also replacing common problematic chars like newline, carriage return, tab
    filename = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', filename)

    # Replace multiple consecutive underscores with a single one
    filename = re.sub(r'_+', '_', filename)

    # Remove leading/trailing underscores that might result from replacement
    filename = filename.strip('_')

    # Limit filename length (optional, but good practice - e.g., 200 chars)
    max_len = 200
    if len(filename) > max_len:
        # Find the last extension part
        base, ext = os.path.splitext(filename)
        # Truncate the base part
        truncated_base = base[:max_len - len(ext) -1] # -1 for the dot
        filename = truncated_base + ext

    # Handle edge case where filename becomes empty after sanitization
    if not filename:
        return "sanitized_empty_filename"

    return filename

# --- Keep generate_picu_treatment_chart and other extract/generate functions ---

def generate_picu_treatment_chart(heading,subheading,json_data,font_size=9):
    """
    Generates a PICU treatment chart PDF from JSON data.

    Args:
        json_data (dict or str): The JSON data containing patient information and treatment details
        output_filename (str): The filename for the generated PDF

    Returns:
        str: Path to the generated PDF file
    """
    print("\n=== Starting PDF Generation Process ===")
    print(f"Input parameters:")
    print(f"- Heading: {heading}")
    print(f"- Subheading: {subheading}")
    print(f"- Font size: {font_size}")
    
    # If json_data is a string, parse it
    if isinstance(json_data, str):
        print("Converting JSON string to dictionary...")
        json_data = json.loads(json_data)

    print("\n=== Extracting Patient Information ===")
    # Extract patient information
    patient_info = extract_patient_info(json_data)
    print(f"Extracted patient info: {patient_info}")

    print("\n=== Extracting Treatment Tables ===")
    # Extract treatment tables
    treatment_tables = extract_entry_tables(json_data)
    print(f"Found {len(treatment_tables)} treatment tables")
    minipage_latex = generate_minipage(treatment_tables)

    print("\n=== Extracting Table Rows ===")
    # Extract table rows
    table_rows = extract_table_rows(json_data)
    print(f"Found {len(table_rows)} table rows")
    latex_table = generate_two_column_table(table_rows)

    print("\n=== Generating PDF ===")
    # Generate the PDF and get the path
    pdf_path = generate_pdf_from_latex(
        heading=heading,
        subheading=subheading,
        patient_info=patient_info,
        treatment_tables=minipage_latex,
        table_rows=latex_table,
        font_size=font_size
    )

    if pdf_path and os.path.exists(pdf_path):
        print(f"\n=== PDF Generation Successful ===")
        print(f"PDF generated at: {pdf_path}")
        print(f"File size: {os.path.getsize(pdf_path)} bytes")
        return pdf_path
    else:
        print("\n=== PDF Generation Failed ===")
        print(f"PDF path: {pdf_path}")
        print(f"File exists: {os.path.exists(pdf_path) if pdf_path else False}")
        return None



def extract_patient_info(json_data):
    """
    Extracts patient information from the JSON data.
    Relies on escape_latex for proper escaping afterwards. # <-- Added comment

    Args:
        json_data (dict): The JSON data containing patient information

    Returns:
        dict: A dictionary containing extracted patient information (escaped)
    """
    # Extract patient information WITHOUT initial escaping for fields handled later
    patient_info_raw = { # Renamed to avoid confusion
        "patient_name": json_data.get("Name", ""),
        "years": int(json_data.get("Age_year", 0)) if json_data.get("Age_year", "").isdigit() else 0,
        "months": int(json_data.get("Age_month", 0)) if json_data.get("Age_month", "").isdigit() else 0,
        "gender": json_data.get("Sex", ""),
        "bed_number": int(json_data.get("bed_number", 0)) if json_data.get("bed_number", "").isdigit() else 0,
        "uhid": json_data.get("uhid", ""),
        # REMOVED .replace() calls here:
        "diagnosis": json_data.get("diagnosis", "").strip(),
        "consultant_names": json_data.get("consultants", "").strip(), # Added strip
        "jr_names": json_data.get("JR", "").strip(),                 # Added strip
        "sr_names": json_data.get("SR", "").strip()                  # Added strip
    }

    # Now, apply escaping using the dedicated function to all string fields
    patient_info_escaped = {} # Create a new dict for escaped values
    for key, value in patient_info_raw.items():
        if isinstance(value, str):
            patient_info_escaped[key] = escape_latex(value)
        else:
            patient_info_escaped[key] = value # Keep non-strings as they are

    # Optional: Print the *final* escaped value being used
    print("????????????????????????????????????????????????????????")
    # Print the value that will actually be used in the template
    print(f"Final escaped diagnosis: {repr(patient_info_escaped.get('diagnosis', ''))}")

    # Return the dictionary containing the FINAL escaped values
    return patient_info_escaped


def extract_entry_tables(json_data):
    """
    Extracts treatment tables from the JSON data and applies LaTeX escaping.

    Args:
        json_data (dict): The JSON data containing treatment information

    Returns:
        list: A list of dictionaries representing treatment tables
    """
    # Get entries from the parameters
    entries = json_data.get("entries", {})
    tables = []

    for entry_key, entry_data in entries.items():
        title = escape_latex(entry_data.get("title", "").strip())  # Escape title
        subtitles = entry_data.get("subtitles", {})

        rows = []
        for subtitle_key, subtitle_data in subtitles.items():
            content = escape_latex(str(subtitle_data.get("content", "")).strip())
            day = escape_latex(str(subtitle_data.get("day", "")).strip())
            dose = escape_latex(str(subtitle_data.get("dose", "")).strip())
            volume = escape_latex(str(subtitle_data.get("volume", "")).strip())

            if any([content, day, dose, volume]):  # Keep row if any field has data
                rows.append((content, day, dose, volume))

        if rows:
            tables.append({
                "title": title,
                "first_header": title,  # Use the title dynamically
                "rows": rows
            })

    return tables



def extract_table_rows(json_data):
    """
    Extracts table rows from the JSON data and applies LaTeX escaping.

    Args:
        json_data (dict): The JSON data containing table row information.

    Returns:
        list: A list of tuples representing table rows.
    """
    # Extract the table row layout data from parameters
    parameters = json_data.get("parameters", {})
    table_data = []

    # Process each row
    for row_key, row_data in parameters.items():
        row_header_name = escape_latex(row_data.get("row_header_name", "").strip())  # Escape header name
        row_header_description = escape_latex(row_data.get("row_header_description", "").strip())  # Escape description

        # Add the row to table_data, ensuring no blank spaces cause issues
        table_data.append((row_header_name, row_header_description if row_header_description else ""))

    return table_data


def generate_minipage(tables):
    """
    Generates LaTeX code for the treatment tables, only including Day/Dose/Volume columns
    if there's content in those fields.
    """
    minipage_code = r"""
"""
    count = 1

    for table in tables:
        table_title = table["title"]
        rows = table["rows"]

        # Check if any row has content in day, dose, or volume columns
        has_day_dose_volume = any(
            any(row[i].strip() for i in [1, 2, 3])  # Check day(1), dose(2), volume(3)
            for row in rows
        )

        if has_day_dose_volume:
            # Full table with all columns
            minipage_code += f"""
    % Medication table with Day/Dose/Volume
    \\begin{{tabular}}{{|p{{7cm}}|p{{1cm}}|p{{2cm}}|p{{2cm}}|}}
        \\hline
        \\textbf{{{table_title}}} & \\textbf{{Day}} & \\textbf{{Dose}} & \\textbf{{Volume}} \\\\
        \\hline
"""
            for row in rows:
                minipage_code += f"       {count}. {row[0]} & {row[1]} & {row[2]} & {row[3]} \\\\\n        \\hline\n"
                count += 1
            minipage_code += r"""    \end{tabular}
    \vspace{0.2cm}
"""
        else:
            # Simplified table without Day/Dose/Volume columns
            minipage_code += f"""
    % Medication table without Day/Dose/Volume
    \\begin{{tabular}}{{|p{{12cm}}|}}
        \\hline
        \\textbf{{{table_title}}} \\\\
        \\hline
"""
            for row in rows:
                minipage_code += f"       {count}. {row[0]} \\\\\n        \\hline\n"
                count += 1
            minipage_code += r"""    \end{tabular}
    \vspace{0.2cm}
"""
        count = 1  # Reset counter for next table

    return minipage_code


def generate_two_column_table(data):
    """
    Generates LaTeX code for the two-column table with improved text wrapping for both label and value.

    Args:
        data (list): A list of tuples representing table rows

    Returns:
        str: LaTeX code for the two-column table
    """
    table_code = r""""""

    # Dynamically adding rows with text wrapping for BOTH columns
    for row in data:
        label, value = row[0], row[1]

        # Split long text into multiple lines
        label = split_string(label, length=9)
        value = split_string(value, length=18)

        if label.lower().strip() == "date":
            table_code += fr" \textbf" + "{" + f"{label}" + "}" + " & " + r" \textbf" + "{" + f"{value}" + "}" + " \\\\\n        \\hline\n"
            continue

        # Wrap both the label and value in minipage environments to force wrapping
        table_code += fr" \begin{{minipage}}[t]{{1.7cm}}\textbf{{{label}}}\end{{minipage}}" + \
                      f" & \\begin{{minipage}}[t]{{2.3cm}}\\raggedright {value} \\end{{minipage}} \\\\\n        \\hline\n"

    return table_code

# sanitize_filename function should be defined above this point


def generate_pdf_from_latex(heading, subheading, patient_info, treatment_tables, table_rows, font_size=13):
    try:
        # Calculate line height based on font size
        line_height = font_size + 2
        header_font_size = font_size + 4
        adjusted_vspace = font_size * 0.1  # Dynamic spacing based on font size

        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Create output directory if it doesn't exist
        output_dir = os.path.join(current_dir, "GENERATED_PDFS")
        os.makedirs(output_dir, exist_ok=True)

        # Generate a unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tex_file_path = os.path.join(output_dir, f"temp_{timestamp}.tex")
        pdf_file_path = os.path.join(output_dir, f"current_{timestamp}.pdf")

        # Process the tables
        left_table = generate_minipage(treatment_tables)
        right_table = generate_two_column_table(table_rows)

        # Check for logo files
    website_logo_path = os.path.join(current_dir, "RESOURCES", "website_logo.png")
    default_logo_path = os.path.join(current_dir, "RESOURCES", "default_AIIMS_LOGO.png")
    
    if os.path.exists(website_logo_path):
        logo_path = "RESOURCES/website_logo.png"
            print("Using website logo")
    else:
        logo_path = "RESOURCES/default_AIIMS_LOGO.png"
            print("Using default logo")

    latex_code = rf"""
\documentclass{{article}}
\usepackage{{graphicx}}
\usepackage[a4paper, margin=0.3in]{{geometry}} % Decreased margins
\usepackage{{array}}
\usepackage{{multirow}}
\usepackage{{tabularx}} % For dynamic column widths
\usepackage{{calc}} % For calculation of lengths
\usepackage[absolute,overlay]{{textpos}} % For absolute positioning
\setlength{{\TPHorizModule}}{{1mm}} % Set horizontal unit to mm
\setlength{{\TPVertModule}}{{1mm}} % Set vertical unit to mm
% Set font size for entire document
\fontsize{{{font_size}pt}}{{{line_height}pt}}\selectfont
% Create a special column type for automatic line breaking
\newcolumntype{{Y}}{{>{{\raggedright\arraybackslash\hspace{{0pt}}\parfillskip=0pt plus 1fil}}p}}
\begin{{document}}\
% Insert logo at the top-left
\noindent
\begin{{minipage}}{{0.2\textwidth}} % Adjust width as needed
    \includegraphics[width=2cm]{{{logo_path}}} % Adjust width as needed
\end{{minipage}}\
\vspace{{-1cm}} % Adjust this value to position the logo at the top
\hfill
\fontsize{{{header_font_size}pt}}{{{header_font_size + 2}pt}}\selectfont % Header font size
\begin{{center}}\
    \textbf{{{heading}}} \\
    \textbf{{{subheading}}} \\
\end{{center}}
\fontsize{{{font_size}pt}}{{{line_height}pt}}\selectfont % Restore main font size
% Keep original upper tables unchanged
\noindent\begin{{tabular}}{{|p{{5cm}}|p{{4cm}}|p{{2.5cm}}|p{{1.5cm}}|p{{3cm}}|}}
    \hline
    \textbf{{Name:}} {patient_info["patient_name"]} & \textbf{{Age:}} {patient_info["years"]} years {patient_info["months"]} months & \textbf{{Gender:}} {patient_info["gender"]} & \textbf{{Bed:}} {patient_info["bed_number"]} & \textbf{{UHID:}} {patient_info["uhid"]} \\
    \hline
    \multicolumn{{5}}{{|p{{19cm}}|}}{{\textbf{{Diagnosis:}} {patient_info["diagnosis"]} }}\\
    \hline
\end{{tabular}}
\\
\\
\noindent\begin{{tabular}}{{|p{{11.3cm}}|p{{7.3cm}}|}}
     \hline
    \textbf{{Consultant:}} {patient_info["consultant_names"]}      & \textbf{{JRs:}} {patient_info["jr_names"]} \\
    \cline{{2-2}}
      & \textbf{{SRs:}} {patient_info["sr_names"]} \\
    \hline
\end{{tabular}}
\vspace{{0.1cm}} % Reduced space
% Create a two-column layout with fixed positions
\noindent
\begin{{minipage}}[t]{{0.45\textwidth}}
\vspace{{-{adjusted_vspace:.2f}cm}} % Dynamic spacing based on font size
{left_table}
\end{{minipage}}%
\hfill%
\begin{{minipage}}[t]{{0.32\textwidth}}
\hspace{{1cm}} % Negative hspace moves content to the left
    % Date information table - fixed on right
    \begin{{tabular}}{{|p{{1.8cm}}|p{{2.5cm}}|}}
    \hline
    {right_table}
    \end{{tabular}}
\end{{minipage}}

% Add signature lines at fixed positions from bottom left
% X=150mm from left, Y=30mm from bottom for JR signature
\begin{{textblock}}{{70}}(150, 267)
    \textbf{{JR Signature:}}
\end{{textblock}}

% X=150mm from left, Y=50mm from bottom for SR signature
\begin{{textblock}}{{70}}(150, 247)
    \textbf{{SR Signature:}}
\end{{textblock}}

\end{{document}}
"""
    # --- Write LaTeX code to the intermediate .tex file ---
    try:
            print("\n=== Writing LaTeX File ===")
            print(f"Writing to: {tex_file_path}")
            with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(latex_code)
            print("LaTeX file written successfully")
    except Exception as e:
            print(f"ERROR: Failed to write LaTeX file: {e}")
            return None

        # --- Compile LaTeX to PDF ---
        try:
            print("\n=== Compiling LaTeX to PDF ===")
            print(f"Using pdflatex at: {pdflatex_path}")
            print(f"Compiling: {tex_file_path}")
            print(f"Output will be: {pdf_file_path}")

            # Run pdflatex with full path and proper error handling
            result = subprocess.run(
                [pdflatex_path, "-interaction=nonstopmode", tex_file_path],
                cwd=output_dir,  # Set working directory to output_dir
                capture_output=True,
                text=True
            )

            # Print compilation output for debugging
            print("\n=== pdflatex Output ===")
            print(result.stdout)
            if result.stderr:
                print("\n=== pdflatex Errors ===")
                print(result.stderr)

            if result.returncode != 0:
                print(f"ERROR: pdflatex compilation failed with return code {result.returncode}")
                return None

            # Check if PDF was generated
            if not os.path.exists(pdf_file_path):
                print(f"ERROR: PDF file not found at {pdf_file_path}")
                return None

            print(f"PDF generated successfully at: {pdf_file_path}")
            return pdf_file_path

        except Exception as e:
            print(f"ERROR: Failed to compile LaTeX: {e}")
            return None

    except Exception as e:
        print(f"ERROR: Unexpected error in generate_pdf_from_latex: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- Keep the __main__ block for testing ---
if __name__ == "__main__":
    # Example with JSON data as a dictionary
    json_data = {
        "uuid": "ddb19471-364d-4e32-ac66-39e7055e5a24",
        "datetime": "23-03-2025 14:49:56",
        "date": "23-03-2025",
        "default_Bed_count": 16,
        "default_Sex_count": 3,
        "default_Entries_count": 5,
        "default_table_rows_count": 5,
        "each_sex_value_names": {
            "Sex_1_name": "Male",
            "Sex_2_name": "Female",
            "Sex_3_name": "Other"
        },
        "Name": "Test Patient<Name>",  # Example with potentially invalid chars
        "Age_year": "78",
        "Age_month": "98",
        "Sex": "Male",
        "uhid": "UHID/123*ABC",  # Example with potentially invalid chars
        "bed_number": "4",
        "diagnosis": "Diagnosis with \\backslash and _underscore.",
        "consultants": "Dr. One & Dr. Two",
        "jr": "Dr. Three",
        "sr": "Dr. Four",
        "each_entry_layout": {
            "entry_1": {
                "title": "Respiratory support",
                "subtitles": {"subtitle_1": {"content": "O2 via NC", "day": "D3", "dose": "2L", "volume": "N/A"}}
            },
            "entry_6": {"title": "Other Medications",
                        "subtitles": {"subtitle_3": {"content": "Med X", "day": "D3", "dose": "20mg", "volume": "3ml"}}}
        },
        "each_table_row_layout": {
            "row_1": {"row_header_name": "Date", "row_header_description": time.strftime("%Y/%m/%d")},
            "row_2": {"row_header_name": "Weight", "row_header_description": "12 kg"}
        }
    }

    generate_picu_treatment_chart('HELLO','WORLD',json_data, font_size=8) # Example font size