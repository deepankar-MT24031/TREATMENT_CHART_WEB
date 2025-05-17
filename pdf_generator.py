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
def escape_latex(text):
    """
    Escapes special LaTeX characters in the given text.
    Handles newlines by converting them to LaTeX newline commands.
    """
    if not isinstance(text, str):
        return text

    # Use a placeholder that does not contain any LaTeX special characters
    placeholder = '<<NEWLINE>>'
    text = text.replace('\n', placeholder)

    # Now replace the placeholder with LaTeX newline
    text = text.replace(placeholder, r'\\')

    # Escape special LaTeX characters (including underscore)
    special_chars = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
        '|': r'\textbar{}',
        '"': r'\textquotedbl{}',
        "'": r'\textquotesingle{}',
        '`': r'\textasciigrave{}'
    }
    for char, escape in special_chars.items():
        text = text.replace(char, escape)

    return text

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

def preprocess_json_text(text):
    """
    Preprocesses text to handle backslashes and newlines properly.
    Only keeps real newlines and replaces all other backslash combinations with underscore.
    """
    if not isinstance(text, str):
        return text
        
    # Replace any literal \n with underscore
    text = text.replace('\\n', '_')
    
    # Replace any other backslash combinations with underscore
    # This will catch things like \t, \r, \b, etc.
    text = re.sub(r'\\(?!n)', '_', text)
    
    return text

def preprocess_json_data(json_data):
    """
    Recursively preprocesses all string values in the JSON data.
    """
    if isinstance(json_data, dict):
        return {k: preprocess_json_data(v) for k, v in json_data.items()}
    elif isinstance(json_data, list):
        return [preprocess_json_data(item) for item in json_data]
    elif isinstance(json_data, str):
        return preprocess_json_text(json_data)
    else:
        return json_data

def generate_picu_treatment_chart(heading, subheading, json_data, font_size=9):
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
    
    # Preprocess the JSON data
    print("\n=== Preprocessing JSON Data ===")
    json_data = preprocess_json_data(json_data)
    
    print("\n=== Extracting Patient Information ===")
    # Extract patient information
    patient_info = extract_patient_info(json_data)
    print(f"Extracted patient info: {patient_info}")

    print("\n=== Extracting Treatment Tables ===")
    # Extract treatment tables
    treatment_tables = extract_entry_tables(json_data)
    print(f"Found {len(treatment_tables)} treatment tables")

    print("\n=== Extracting Table Rows ===")
    # Extract table rows
    table_rows = extract_table_rows(json_data)
    print(f"Found {len(table_rows)} table rows")

    print("\n=== Generating PDF ===")
    # Generate the PDF and get the path
    pdf_path = generate_pdf_from_latex(
        heading=heading,
        subheading=subheading,
        patient_info=patient_info,
        treatment_tables=treatment_tables,  # Pass the raw tables, not the LaTeX code
        table_rows=table_rows,  # Pass the raw rows, not the LaTeX code
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
        # Updated field names to match frontend capitalization
        "diagnosis": json_data.get("Diagnosis", "").strip(),
        "consultant_names": json_data.get("Consultants", "").strip(),
        "jr_names": json_data.get("JR", "").strip(),
        "sr_names": json_data.get("SR", "").strip()
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
    Returns a list of dicts, each with 'title', 'rows', and 'columns' (list of present columns, in order if specified).
    """
    entries = json_data.get("entries", {})
    tables = []

    for entry_key, entry_data in entries.items():
        title = escape_latex(entry_data.get("title", "").strip())
        subtitles = entry_data.get("subtitles", {})

        # Use columns array from JSON if present, otherwise infer
        if "columns" in entry_data and isinstance(entry_data["columns"], list):
            columns = ["content"] + [col for col in entry_data["columns"] if col != "content"]
        else:
            # fallback: infer from subtitles
            present_columns = set(["content"])
            for subtitle_key, subtitle_data in subtitles.items():
                for col in ["day", "dose", "volume", "rate"]:
                    if col in subtitle_data:
                        present_columns.add(col)
            columns = list(present_columns)

        rows = []
        for subtitle_key, subtitle_data in subtitles.items():
            row = {"content": escape_latex(str(subtitle_data.get("content", "")).strip())}
            for col in columns:
                if col == "content":
                    continue
                if col in subtitle_data:
                    row[col] = escape_latex(str(subtitle_data.get(col, "")).strip())
            # Only keep row if any field has data
            if any(row.get(col, "") for col in row):
                rows.append(row)
        if rows:
            tables.append({
                "title": title,
                "rows": rows,
                "columns": columns
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
    Generates LaTeX code for the treatment tables using tabularx.
    The first "content" (title/description) column is an 'X' (flexible) column
    and is prioritized to be significantly wider.
    There can be up to 3 additional "extra" columns with a very narrow, fixed width.
    All tables span the full width of their parent minipage.
    """
    minipage_code = r""
    
    for table_idx, table in enumerate(tables):
        main_column_header = table["title"] 
        rows = table["rows"]
        columns_in_data = table["columns"] 

        # --- SKIP TABLES WITH NO COLUMNS OR NO ROWS ---
        if not columns_in_data or not rows:
            continue
                                        
        headers_list = []
        col_specs_list = []
        data_keys_for_rows_ordered = []

        # 1. The main descriptive column ("content" / "title" column)
        # This will be the 'X' column. It will get the lion's share of the space.
        if "content" in columns_in_data:
            col_specs_list.append(">{\\raggedright\\arraybackslash}X") 
            headers_list.append(f"\\textbf{{{main_column_header}}}")
            data_keys_for_rows_ordered.append("content")
        else: # Fallback (should ideally not be hit if 'content' is always present)
            if columns_in_data:
                first_key = columns_in_data[0]
                col_specs_list.append(">{\\raggedright\\arraybackslash}X")
                headers_list.append(f"\\textbf{{{first_key.capitalize()}}}")
                data_keys_for_rows_ordered.append(first_key)
            else: # No columns at all in data
                col_specs_list.append(">{\\raggedright\\arraybackslash}X") 
                headers_list.append(f"\\textbf{{{main_column_header}}}") # Still use the table title as header

        # 2. Handle "extra" columns (day, dose, volume, rate, etc.)
        # 'day' column gets 1.0cm, all others get 2.0cm
        temp_extra_cols_specs = []
        temp_extra_cols_headers = []
        temp_extra_cols_keys = []

        current_main_col_key = data_keys_for_rows_ordered[0] if data_keys_for_rows_ordered else None

        for col_key in columns_in_data:
            if col_key == current_main_col_key:
                continue
            # Special width for 'day', default for others
            if col_key == "day":
                col_width = "0.7cm"
            else:
                col_width = "1.2cm"  # Reduced from 2.0cm to make main column wider
            temp_extra_cols_specs.append(f">{{\\raggedright\\arraybackslash}}p{{{col_width}}}")
            temp_extra_cols_headers.append(f"\\textbf{{{col_key.capitalize()}}}")
            temp_extra_cols_keys.append(col_key)

        col_specs_list.extend(temp_extra_cols_specs)
        headers_list.extend(temp_extra_cols_headers)
        data_keys_for_rows_ordered.extend(temp_extra_cols_keys)
            
        final_col_spec = "|" + "|".join(col_specs_list) + "|" if col_specs_list else "|>{\\raggedright\\arraybackslash}X|"
        
        minipage_code += f"""
    % Medication table '{main_column_header}' (PRIORITIZED WIDE TITLE COLUMN)
    \\noindent
    \\begin{{tabularx}}{{\\linewidth}}{{{final_col_spec}}}
        \\hline
"""
        if headers_list:
            minipage_code += "        " + " & ".join(headers_list) + r" \\" + "\n        \\hline\n"

        for item_num, row_data in enumerate(rows):
            row_cells = []
            if data_keys_for_rows_ordered:
                main_desc_key = data_keys_for_rows_ordered[0]
                item_description = row_data.get(main_desc_key, '') 
                row_cells.append(f"{item_num + 1}. {item_description}") # This goes into the X column

                # Data for the narrow extra columns
                for extra_col_key in data_keys_for_rows_ordered[1:]:
                    cell_text = row_data.get(extra_col_key, '')
                    row_cells.append(cell_text)
            else: # No columns defined in spec, but row data might exist
                row_cells.append(f"{item_num + 1}. ") # Default for malformed cases

            minipage_code += "        " + " & ".join(row_cells) + r" \\" + "\n        \\hline\n"
        
        minipage_code += r"""    \end{tabularx}
    \vspace{0.2cm}
"""
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
        # Detect pdflatex path
        if sys.platform == 'win32':
            pdflatex_path = r"C:\texlive\2023\bin\win32\pdflatex.exe"
            if not os.path.exists(pdflatex_path):
                pdflatex_path = r"C:\texlive\2022\bin\win32\pdflatex.exe"
        else:
            pdflatex_path = "/usr/local/bin/pdflatex"
            if not os.path.exists(pdflatex_path):
                pdflatex_path = "/usr/bin/pdflatex"

        if not os.path.exists(pdflatex_path):
            print(f"ERROR: pdflatex not found at {pdflatex_path}")
            return None

        # Calculate line height based on font size
        line_height = font_size + 2
        header_font_size = font_size + 4
        subheader_font_size = font_size + 2  # Smaller than header
        adjusted_vspace = font_size * 0.19  # Increased upward shift, still dynamic with font size

        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Create output directory if it doesn't exist
        output_dir = os.path.join(current_dir, "GENERATED_PDFS")
        os.makedirs(output_dir, exist_ok=True)

        # Generate a unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"current_{timestamp}"
        tex_file_path = os.path.join(output_dir, f"{base_filename}.tex")
        pdf_file_path = os.path.join(output_dir, f"{base_filename}.pdf")

        # Process the tables into LaTeX code
        left_table = generate_minipage(treatment_tables)
        right_table = generate_two_column_table(table_rows)

        # Check for logo files
        website_logo_path = os.path.join(current_dir, "RESOURCES", "website_logo.png")
        default_logo_path = os.path.join(current_dir, "RESOURCES", "default_AIIMS_LOGO.png")
        
        if os.path.exists(website_logo_path):
            logo_path = website_logo_path  # Use absolute path
            print("Using website logo")
        else:
            logo_path = default_logo_path  # Use absolute path
            print("Using default logo")

        # Create a copy of the logo in the output directory
        logo_filename = os.path.basename(logo_path)
        logo_copy_path = os.path.join(output_dir, logo_filename)
        try:
            shutil.copy2(logo_path, logo_copy_path)
            print(f"Copied logo to: {logo_copy_path}")
        except Exception as e:
            print(f"Warning: Failed to copy logo: {e}")
            logo_copy_path = logo_path  # Fall back to original path

        # ---- ADJUST MINIPAGE WIDTHS AND POSITIONING HERE ----
        # Increase the space between the left and right tables
        left_minipage_width_fraction = 0.73 # Slightly narrower left table
        right_minipage_width_fraction = 0.26  # Slightly wider right table, moved a bit left
        
        # Important: Use \hfill instead of fixed spacing to push right table to the far right
        
        latex_code = rf"""
\documentclass{{article}}
\usepackage{{graphicx}}
\usepackage[a4paper, margin=0.3in]{{geometry}} 
\usepackage{{array}}
\usepackage{{multirow}}
\usepackage{{tabularx}} 
\usepackage{{calc}} 
\usepackage[absolute,overlay]{{textpos}} 
\usepackage{{multicol}}
\setlength{{\TPHorizModule}}{{1mm}} 
\setlength{{\TPVertModule}}{{1mm}} 
\fontsize{{{font_size}pt}}{{{line_height}pt}}\selectfont
\newcolumntype{{Y}}{{>{{\raggedright\arraybackslash\hspace{{0pt}}\parfillskip=0pt plus 1fil}}p}}
\begin{{document}}
% Insert logo at the top-left
\noindent
\begin{{minipage}}{{0.2\textwidth}} % Adjust width as needed
    \includegraphics[width=2cm]{{{logo_filename}}} % Use just the filename
\end{{minipage}}\
\vspace{{-1cm}} % Adjust this value to position the logo at the top
\hfill
\begin{{center}}\
    \fontsize{{{header_font_size}pt}}{{{header_font_size + 2}pt}}\selectfont % Header font size
    \textbf{{{heading}}} \\
    \fontsize{{{subheader_font_size}pt}}{{{subheader_font_size + 2}pt}}\selectfont % Subheader font size
    \textbf{{{subheading}}} \\
\end{{center}}
\fontsize{{{font_size}pt}}{{{line_height}pt}}\selectfont % Restore main font size
% Keep original upper tables unchanged
\noindent\begin{{tabular}}{{|p{{5cm}}|p{{4cm}}|p{{2.5cm}}|p{{1.5cm}}|p{{3cm}}|}}
    \hline
    \textbf{{Name:}} {patient_info["patient_name"]} & \textbf{{Age:}} {patient_info["years"]} years {patient_info["months"]} months & \textbf{{Gender:}} {patient_info["gender"]} & \textbf{{Bed:}} {patient_info["bed_number"]} & \textbf{{UHID:}} {patient_info["uhid"]} \\
    \hline
    \multicolumn{{5}}{{|p{{19cm}}|}}{{\textbf{{Diagnosis:}} \parbox[t]{{18cm}}{{{patient_info["diagnosis"]}\vspace{{0.3em}}}}}} \\
    \hline
\end{{tabular}}
\\
\\
\noindent\begin{{tabular}}{{|p{{11.3cm}}|p{{7.3cm}}|}}
     \hline
    \textbf{{Consultant:}} \parbox[t]{{10.5cm}}{{{patient_info["consultant_names"]}\vspace{{0.3em}}}}      & \textbf{{JRs:}} \parbox[t]{{6.5cm}}{{{patient_info["jr_names"]}\vspace{{0.3em}}}} \\
    \cline{{2-2}}
      & \textbf{{SRs:}} \parbox[t]{{6.5cm}}{{{patient_info["sr_names"]}\vspace{{0.3em}}}} \\
    \hline
\end{{tabular}}
\vspace{{0.1cm}} % Reduced space

% FIXED LAYOUT: Use parallel columns instead of minipages
\begin{{multicols}}{{2}}
\columnsep=60pt
\noindent
{left_table}
\columnbreak
\noindent
\hspace*{{4.5cm}}% extra space to push right table further right
\begin{{tabular}}{{|p{{1.8cm}}|p{{2.5cm}}|}} % The widths INSIDE this table 
\hline
{right_table}
\end{{tabular}}
\end{{multicols}}

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
                [pdflatex_path, "-jobname", base_filename, "-interaction=nonstopmode", tex_file_path],
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
    
    # Ensure it returns pdf_path at the end if successful
    if 'result' in locals() and result.returncode == 0 and os.path.exists(pdf_file_path):
        print(f"PDF generated successfully at: {pdf_file_path}")
        return pdf_file_path
    else:
        # Attempt to find pdf_file_path if it was created before an error
        if 'pdf_file_path' in locals() and os.path.exists(pdf_file_path):
             print(f"PDF may have been generated at: {pdf_file_path}, but an error occurred later.")
             return pdf_file_path
        print(f"ERROR: PDF generation failed or an error occurred.")
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