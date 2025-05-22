# START OF FILE external_database_handler.py

import psycopg2
import json
from datetime import datetime as dt
import hashlib
import re # For robust space normalization

# --- Helper Function for Text Normalization ---
def normalize_diagnosis_text(text_raw):
    """Normalizes diagnosis text for consistent hashing."""
    if not text_raw:
        return "n/a" # Default for empty or None, already lowercase
    
    # 1. Convert to lowercase
    text = text_raw.lower()
    # 2. Strip leading/trailing whitespace
    text = text.strip()
    # 3. Replace multiple internal spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    if not text: # If text was only whitespace and became empty
        return "n/a"
    return text
# --- End Helper Function ---


# --- Database Interaction Functions ---

def insert_patient(cur, data):
    """
    Inserts or updates a patient record, updating last_updated timestamp,
    and returns the patient's PK uuid.
    """
    application_uuid_from_json = data.get("uuid")
    if not application_uuid_from_json:
        raise ValueError("Application UUID (from JSON 'uuid' field) is missing but required.")

    bed_number_raw = data.get("Bed_Number", data.get("bed_number"))
    bed_number_val = None
    if bed_number_raw is not None and str(bed_number_raw).strip() != "":
        try:
            bed_number_val = int(bed_number_raw)
        except ValueError:
            print(f"Warning: Bed_Number '{bed_number_raw}' is not a valid integer. Storing bed_number as NULL.")
    else:
        pass # bed_number_val remains None

    # The last_updated column will be set by the database using CURRENT_TIMESTAMP
    # or the trigger. Explicitly setting it here for clarity and consistency.
    cur.execute("""
        INSERT INTO treatment_chart.patient
            (uhid, name, age_in_months, age_in_years, sex, application_uuid, bed_number, last_updated)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (uhid) DO UPDATE SET
            name = EXCLUDED.name,
            age_in_months = EXCLUDED.age_in_months,
            age_in_years = EXCLUDED.age_in_years,
            sex = EXCLUDED.sex,
            application_uuid = EXCLUDED.application_uuid,
            bed_number = EXCLUDED.bed_number,
            last_updated = CURRENT_TIMESTAMP -- Explicitly update on conflict
        RETURNING uuid, last_updated; -- Return the UUID and the new last_updated timestamp
    """, (
        data.get("uhid"),
        data.get("Name"),
        data.get("Age_month"),
        data.get("Age_year"),
        data.get("Sex"),
        application_uuid_from_json,
        bed_number_val
    ))
    result = cur.fetchone()
    patient_pk_uuid = result[0]
    last_updated_ts = result[1] # The timestamp set by the database

    print(f"Patient PK (DB-generated or existing): {patient_pk_uuid} (App UUID from JSON: {application_uuid_from_json}), Bed Number in DB: {bed_number_val}, Last Updated: {last_updated_ts}")
    return patient_pk_uuid # Return only patient_pk_uuid as per original script's expectation for this function's return

def insert_diagnosis(cur, data, fk_patient_uuid):
    """
    Inserts a new diagnosis record or updates an existing one (if matched by hash)
    to refresh its last_updated timestamp and consultant details.
    Returns its diagnosis_id (PK).
    """
    new_diagnosis_text_raw = data.get("Diagnosis") or data.get("diagnosis")
    
    # Normalize the incoming diagnosis text
    new_diagnosis_text_normalized = normalize_diagnosis_text(new_diagnosis_text_raw)

    # Calculate the hash of the normalized diagnosis text
    new_diagnosis_hash = hashlib.sha256(new_diagnosis_text_normalized.encode('utf-8')).hexdigest()
    print(f"  Incoming diagnosis for patient {fk_patient_uuid}: '{new_diagnosis_text_raw}' (Normalized & Hashed As: '{new_diagnosis_text_normalized}', Hash: {new_diagnosis_hash})")

    # Fetch existing diagnosis_id and diagnosis_text for this patient
    cur.execute("""
        SELECT diagnosis_id, diagnosis_text
        FROM treatment_chart.diagnosis
        WHERE patient_uuid = %s;
    """, (fk_patient_uuid,))
    existing_diagnoses_for_patient = cur.fetchall()

    found_diagnosis_pk_id = None
    if existing_diagnoses_for_patient:
        print(f"  Found {len(existing_diagnoses_for_patient)} existing diagnoses for patient {fk_patient_uuid}. Checking hashes (normalized)...")
        for D_pk_id, D_text_from_db_raw in existing_diagnoses_for_patient:
            # Normalize text from DB for comparison
            D_text_from_db_normalized = normalize_diagnosis_text(D_text_from_db_raw)
            existing_entry_hash = hashlib.sha256(D_text_from_db_normalized.encode('utf-8')).hexdigest()
            if existing_entry_hash == new_diagnosis_hash:
                found_diagnosis_pk_id = D_pk_id
                print(f"  MATCH FOUND: Will update existing Diagnosis PK: {found_diagnosis_pk_id} for patient {fk_patient_uuid} (Original DB Text: '{D_text_from_db_raw}')")
                break

    if found_diagnosis_pk_id:
        # Update the last_updated timestamp and consultant details for the existing diagnosis.
        # The DB trigger will also set last_updated, but explicit set here is fine.
        print(f"  Updating existing Diagnosis PK: {found_diagnosis_pk_id} to refresh its timestamp and consultants.")
        cur.execute("""
            UPDATE treatment_chart.diagnosis
            SET 
                consultants = %s,
                jr = %s,
                sr = %s,
                last_updated = CURRENT_TIMESTAMP 
            WHERE diagnosis_id = %s
            RETURNING diagnosis_id, last_updated;
        """, (
            data.get("Consultants") or data.get("consultants"),
            data.get("JR") or data.get("jr"),
            data.get("SR") or data.get("sr"),
            found_diagnosis_pk_id
        ))
        updated_result = cur.fetchone()
        # diagnosis_id will be the same, but we get the new last_updated
        updated_diagnosis_id = updated_result[0]
        updated_diagnosis_ts = updated_result[1]
        print(f"  Diagnosis PK {updated_diagnosis_id} updated. New last_updated: {updated_diagnosis_ts}")
        return updated_diagnosis_id
    else:
        if existing_diagnoses_for_patient:
             print(f"  NO MATCH: No existing diagnosis for patient {fk_patient_uuid} matched the hash. Inserting new.")
        else:
             print(f"  NO EXISTING DIAGNOSES: No prior diagnoses for patient {fk_patient_uuid}. Inserting new.")

        # Store the ORIGINAL raw text (or "N/A" if it was truly empty/None initially)
        text_to_store = new_diagnosis_text_raw if new_diagnosis_text_raw and new_diagnosis_text_raw.strip() else "N/A"

        # last_updated will be set by CURRENT_TIMESTAMP on insert.
        cur.execute("""
            INSERT INTO treatment_chart.diagnosis (patient_uuid, diagnosis_text, consultants, jr, sr, last_updated)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING diagnosis_id;
        """, (
            fk_patient_uuid,
            text_to_store,
            data.get("Consultants") or data.get("consultants"),
            data.get("JR") or data.get("jr"),
            data.get("SR") or data.get("sr")
        ))
        diagnosis_pk_id = cur.fetchone()[0]
        print(f"  NEW Diagnosis PK (DB-generated): {diagnosis_pk_id}, linked to Patient PK: {fk_patient_uuid} for text '{text_to_store}'")
        return diagnosis_pk_id


def insert_observation(cur, data, fk_diagnosis_id, each_table_row_layout_data):
    """
    Inserts an observation record and returns its observation_id (PK).
    prescription_date and prescription_time are extracted from each_table_row_layout's 'row_header_description'.
    Other metrics are also extracted from each_table_row_layout's 'row_header_description'.
    The entire `each_table_row_layout_data` is stored as JSON in the `extra_metric` column.
    created_at is auto-generated by the DB.
    """
    prescription_date_val = None
    prescription_time_val = None
    weight_val = None
    length_val = None
    bsa_val = None
    tfr_val = None
    tfv_val = None
    ivm_val = None
    ivf_val = None
    feeds_val = None
    gir_mg_kg_min_val = None
    k_plus_val = None
    egfr_val = None

    if each_table_row_layout_data:
        for row_key, row_details in each_table_row_layout_data.items():
            header_name = row_details.get("row_header_name", "").strip().lower()
            value_from_description = row_details.get("row_header_description", "").strip()

            if value_from_description: 
                if header_name == "date":
                    prescription_date_val = value_from_description
                elif header_name == "time":
                    prescription_time_val = value_from_description
                elif header_name == "weight":
                    weight_val = value_from_description
                elif header_name == "length":
                    length_val = value_from_description
                elif header_name == "bsa":
                    bsa_val = value_from_description
                elif header_name == "tfr":
                    tfr_val = value_from_description
                elif header_name == "tfv":
                    tfv_val = value_from_description
                elif header_name == "ivm":
                    ivm_val = value_from_description
                elif header_name == "ivf":
                    ivf_val = value_from_description
                elif header_name == "feeds":
                    feeds_val = value_from_description
                elif header_name == "gir(mg/kg/min)":
                    gir_mg_kg_min_val = value_from_description
                elif header_name == "k+":
                    k_plus_val = value_from_description
                elif header_name == "egfr":
                    egfr_val = value_from_description

    if prescription_date_val is None:
        prescription_date_val = "N/A" 
        print("Warning: Prescription Date not found or empty in each_table_row_layout. Using default 'N/A'.")
    if prescription_time_val is None:
        prescription_time_val = "N/A" 
        print("Warning: Prescription Time not found or empty in each_table_row_layout. Using default 'N/A'.")

    extra_metric_json_content = None
    if each_table_row_layout_data: 
        try:
            extra_metric_json_content = json.dumps(each_table_row_layout_data)
        except TypeError as te:
            print(f"Warning: Could not serialize each_table_row_layout_data to JSON for extra_metric: {te}. Storing NULL.")
    else:
        print("Warning: `each_table_row_layout_data` is empty or None. `extra_metric` will be stored as NULL (or empty JSON if column requires it).")

    cur.execute("""
        INSERT INTO treatment_chart.observation (
            diagnosis_id, prescription_date, prescription_time,
            weight, length, bsa, tfr, tfv, ivm, ivf,
            feeds, gir_mg_kg_min, k_plus, egfr, extra_metric
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING observation_id, created_at;
    """, (
        fk_diagnosis_id, prescription_date_val, prescription_time_val,
        weight_val, length_val, bsa_val, tfr_val, tfv_val, ivm_val, ivf_val,
        feeds_val, gir_mg_kg_min_val, k_plus_val, egfr_val, 
        extra_metric_json_content 
    ))
    result = cur.fetchone()
    observation_pk_id = result[0]
    created_at_timestamp = result[1]
    print(f"Observation PK (DB-generated): {observation_pk_id}, Linked to Diagnosis PK: {fk_diagnosis_id}, Created At (DB): {created_at_timestamp}")
    print(f"  Prescription Date: {prescription_date_val}, Prescription Time: {prescription_time_val}")
    if extra_metric_json_content:
        print(f"  Stored `each_table_row_layout_data` as JSON in observation.extra_metric.")
    else:
        print(f"  `observation.extra_metric` stored as NULL (or default empty JSON).")
    return observation_pk_id

def insert_extra_table_layouts(cur, data, fk_observation_id):
    """
    Archives ONLY the original `each_entry_layout` into the extra_table.
    """
    each_entry_layout_data = data.get("each_entry_layout") 
    
    if each_entry_layout_data: 
        try:
            json_content_for_extra_table = json.dumps(each_entry_layout_data)
            cur.execute("""
                INSERT INTO treatment_chart.extra_table (observation_id, json_content)
                VALUES (%s, %s);
            """, (fk_observation_id, json_content_for_extra_table))
            print(f"Stored `each_entry_layout` in extra_table for Observation PK: {fk_observation_id}")
        except TypeError as te:
            print(f"Error serializing `each_entry_layout` to JSON for extra_table: {te}")
    else:
        print(f"`each_entry_layout` not found or empty. No record inserted into extra_table.")


# --- Detail Table Insertion Functions ---
def insert_respiratory_support(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Respiratory Support ===")
    print(f"Content: {content}")
    print(f"Rate: {subtitle_data.get('rate')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.respiratory_support (observation_id, content, rate, volume) VALUES (%s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("rate"), subtitle_data.get("volume")))
    print("✓ Respiratory support record saved")

def insert_sedation(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Sedation ===")
    print(f"Content: {content}")
    print(f"Dose: {subtitle_data.get('dose')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.sedation (observation_id, content, dose, volume) VALUES (%s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("dose"), subtitle_data.get("volume")))
    print("✓ Sedation record saved")

def insert_inotropes(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Inotropes ===")
    print(f"Content: {content}")
    print(f"Dose: {subtitle_data.get('dose')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.inotropes (observation_id, content, dose, volume) VALUES (%s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("dose"), subtitle_data.get("volume")))
    print("✓ Inotropes record saved")

def insert_antimicrobials(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Antimicrobials ===")
    print(f"Content: {content}")
    print(f"Day: {subtitle_data.get('day')}")
    print(f"Dose: {subtitle_data.get('dose')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.antimicrobials (observation_id, content, day, dose, volume) VALUES (%s, %s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("day"), subtitle_data.get("dose"), subtitle_data.get("volume")))
    print("✓ Antimicrobials record saved")

def insert_iv_fluid(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting IV Fluid ===")
    print(f"Content: {content}")
    print(f"Rate: {subtitle_data.get('rate')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.iv_fluid (observation_id, content, rate, volume) VALUES (%s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("rate"), subtitle_data.get("volume")))
    print("✓ IV fluid record saved")

def insert_feeds(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Feeds ===")
    print(f"Content: {content}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.feeds (observation_id, content, volume) VALUES (%s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("volume")))
    print("✓ Feeds record saved")

def insert_other_medications(cur, fk_observation_id, subtitle_data):
    content = subtitle_data.get("content","").strip()
    if not content: return
    print(f"\n=== Inserting Other Medications ===")
    print(f"Content: {content}")
    print(f"Dose: {subtitle_data.get('dose')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    cur.execute("INSERT INTO treatment_chart.other_medications (observation_id, content, dose, volume) VALUES (%s, %s, %s, %s);",
                (fk_observation_id, content, subtitle_data.get("dose"), subtitle_data.get("volume")))
    print("✓ Other medications record saved")

def insert_supportive_care(cur, fk_observation_id, subtitle_data):
    """Inserts a supportive care record."""
    content = subtitle_data.get("content","").strip()
    if not content: return # Do not insert if content is empty
    
    print(f"\n=== Inserting Supportive Care ===")
    print(f"Content: {content}")
    print(f"Rate: {subtitle_data.get('rate')}")
    print(f"Volume: {subtitle_data.get('volume')}")
    
    cur.execute("""
        INSERT INTO treatment_chart.supportive_care (observation_id, content, rate, volume) 
        VALUES (%s, %s, %s, %s);
    """,(
        fk_observation_id, 
        content, 
        subtitle_data.get("rate"),
        subtitle_data.get("volume")
    ))
    print("✓ Supportive care record saved")


# --- Main Processing Logic ---
def process_json_data(json_input_str_or_dict):
    if isinstance(json_input_str_or_dict, str):
        data = json.loads(json_input_str_or_dict)
    elif isinstance(json_input_str_or_dict, dict):
        data = json_input_str_or_dict
    else:
        raise TypeError("Input must be a JSON string or a Python dictionary.")

    print("\n=== Input Data Structure ===")
    print("Keys in input data:", list(data.keys()))
    
    if "parameters" in data and "each_table_row_layout" not in data:
        print("\n=== Transforming parameters to each_table_row_layout ===")
        data["each_table_row_layout"] = data.pop("parameters")
        print("Transformed parameters to each_table_row_layout")
        print("New keys:", list(data.keys()))
    
    if "entries" in data and "each_entry_layout" not in data:
        print("\n=== Transforming entries to each_entry_layout ===")
        data["each_entry_layout"] = data.pop("entries")
        print("Transformed entries to each_entry_layout")
        print("New keys:", list(data.keys()))

    db_params = {
        "dbname": "mydb",
        "user": "admin",
        "password": "admin",
        "host": "treatment_chart_db", # Changed for Docker internal networking
        "port": "5432"
    }

    print("\n=== PostgreSQL Connection Parameters ===")
    print(f"Database: {db_params['dbname']}")
    print(f"Host: {db_params['host']}")
    print(f"Port: {db_params['port']}")
    print(f"User: {db_params['user']}")

    conn = None
    cur = None

    try:
        print("\n=== Attempting Database Connection ===")
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        print("✓ Successfully connected to PostgreSQL database")

        print("\n=== Starting Data Insertion Process ===")
        print("1. Inserting/Updating Patient Record...")
        patient_pk_uuid = insert_patient(cur, data) # This now returns only the UUID
        print(f"✓ Patient record processed with UUID: {patient_pk_uuid}")

        print("\n2. Inserting/Finding Diagnosis Record...")
        diagnosis_pk_id = insert_diagnosis(cur, data, patient_pk_uuid)
        print(f"✓ Diagnosis record processed with ID: {diagnosis_pk_id}")

        each_entry_layout_data = data.get("each_entry_layout", {}) 
        each_table_row_layout_data = data.get("each_table_row_layout", {})
        
        print("\n3. Inserting Observation Record...")
        observation_pk_id = insert_observation(cur, data, diagnosis_pk_id,
                                               each_table_row_layout_data)
        print(f"✓ Observation record created with ID: {observation_pk_id}")

        print("\n4. Archiving `each_entry_layout` Data (into extra_table)...")
        insert_extra_table_layouts(cur, data, observation_pk_id) 

        if each_entry_layout_data: 
            print("\n5. Processing Treatment Details...")
            treatment_count = 0
            for entry_key, entry_value in each_entry_layout_data.items():
                title = entry_value.get("title", "").strip().lower()
                subtitles_dict = entry_value.get("subtitles")
                if not subtitles_dict:
                    continue
                
                subtitle_data = subtitles_dict.get("subtitle_1", {})
                if not subtitle_data: 
                    continue
                
                print(f"\n   Processing treatment: {title}")
                if title == "respiratory support":
                    insert_respiratory_support(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "sedation, analgesia, and neuromuscular blockade":
                    insert_sedation(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "inotropes and anti-hypertensives":
                    insert_inotropes(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "antimicrobials":
                    insert_antimicrobials(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "iv fluid":
                    insert_iv_fluid(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "feeds":
                    insert_feeds(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "other medications":
                    insert_other_medications(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
                elif title == "supportive care":
                    insert_supportive_care(cur, observation_pk_id, subtitle_data)
                    treatment_count += 1
            print(f"✓ Processed {treatment_count} treatment records")

        print("\n=== Committing Transaction ===")
        conn.commit()
        print("✓ All changes committed successfully!")
        print("\n=== Data Insertion Complete ===")
        print(f"Summary:")
        print(f"- Patient UUID: {patient_pk_uuid}")
        print(f"- Diagnosis ID: {diagnosis_pk_id}")
        print(f"- Observation ID: {observation_pk_id}")

    except psycopg2.Error as e:
        if conn: 
            print("\n=== Rolling Back Transaction ===")
            conn.rollback()
            print("✓ Transaction rolled back due to error")
        print(f"\n❌ Database error: {e}")
        if hasattr(cur, 'query') and cur.query: 
            print(f"Failed query: {cur.query}")
    except ValueError as ve:
        if conn: 
            print("\n=== Rolling Back Transaction ===")
            conn.rollback()
            print("✓ Transaction rolled back due to validation error")
        print(f"\n❌ Data validation error: {ve}")
    except Exception as e:
        if conn: 
            print("\n=== Rolling Back Transaction ===")
            conn.rollback()
            print("✓ Transaction rolled back due to unexpected error")
        print(f"\n❌ An unexpected error occurred: {e}")
    finally:
        if cur: 
            print("\n=== Closing Database Cursor ===")
            cur.close()
            print("✓ Cursor closed")
        if conn: 
            print("\n=== Closing Database Connection ===")
            conn.close()
            print("✓ Connection closed")

# --- Example Usage ---
if __name__ == "__main__":
    # First run for patient 1, diagnosis A
    json_data_patient1_diagA_obs1 = {
        'uuid': 'patient-app-uuid-P1',
        'Name': 'Patient Alpha',
        'Age_year': '10', 'Age_month': '1', 'Sex': 'M', 'uhid': 'UHID-P1',
        'Bed_Number': '101', 
        'Diagnosis': 'Common Cold', 
        'Consultants': 'Dr. One', 'JR': 'Jr. A', 'SR': 'Sr. X',
        'each_table_row_layout': {
            'row_1': {'row_header_name': 'Date', 'row_header_description': '2024-01-01'},
            'row_2': {'row_header_name': 'Time', 'row_header_description': '09:00 AM'}
        }
    }
    print("\n\n--- Processing Patient 1, Diagnosis A, Observation 1 ---")
    process_json_data(json_data_patient1_diagA_obs1)

    # Second run for patient 1, SAME diagnosis A (different spacing/casing), new observation, different bed number
    # Consultant details might change or stay the same for the SAME diagnosis if re-confirmed
    json_data_patient1_diagA_obs2 = {
        'uuid': 'patient-app-uuid-P1', 
        'Name': 'Patient Alpha', 
        'Age_year': '10', 'Age_month': '1', 'Sex': 'M', 'uhid': 'UHID-P1',
        'Bed_Number': '102', 
        'Diagnosis': '  common   cold  ', 
        'Consultants': 'Dr. Uno', 'JR': 'Jr. B', 'SR': 'Sr. Y', # Updated consultants for the same diagnosis
        'each_table_row_layout': {
            'row_1': {'row_header_name': 'Date', 'row_header_description': '2024-01-02'},
            'row_2': {'row_header_name': 'Time', 'row_header_description': '10:00 AM'}
        }
    }
    print("\n\n--- Processing Patient 1, Diagnosis A (again, normalized, updated consultants), Observation 2, Updated Bed ---")
    process_json_data(json_data_patient1_diagA_obs2)

    # Third run for patient 1, DIFFERENT diagnosis B, new observation, invalid bed number
    json_data_patient1_diagB_obs1 = {
        'uuid': 'patient-app-uuid-P1',
        'Name': 'Patient Alpha',
        'Age_year': '10', 'Age_month': '1', 'Sex': 'M', 'uhid': 'UHID-P1',
        'Bed_Number': 'A-205', 
        'Diagnosis': 'Mild Fever', 
        'Consultants': 'Dr. Two', 'JR': 'Jr. C', 'SR': 'Sr. Z',
        'each_table_row_layout': {
            'row_1': {'row_header_name': 'Date', 'row_header_description': '2024-01-03'},
            'row_2': {'row_header_name': 'Time', 'row_header_description': '11:00 AM'}
        }
    }
    print("\n\n--- Processing Patient 1, Diagnosis B, Observation 1, Invalid Bed ---")
    process_json_data(json_data_patient1_diagB_obs1)

    # Fourth run for DIFFERENT patient 2, with a diagnosis text SAME as P1's Diag A
    json_data_patient2_diagA_obs1 = {
        'uuid': 'patient-app-uuid-P2',
        'Name': 'Patient Beta',
        'Age_year': '20', 'Age_month': '2', 'Sex': 'F', 'uhid': 'UHID-P2',
        'Bed_Number': '201', 
        'Diagnosis': 'Common Cold', 
        'Consultants': 'Dr. Three',
        'each_table_row_layout': {
            'row_1': {'row_header_name': 'Date', 'row_header_description': '2024-01-04'},
            'row_2': {'row_header_name': 'Time', 'row_header_description': '12:00 PM'}
        }
    }
    print("\n\n--- Processing Patient 2, Diagnosis A text (normalized), Observation 1 ---")
    process_json_data(json_data_patient2_diagA_obs1)
    
    # Fifth run: Patient 1, "Supportive Care" example, Bed_Number might be empty string
    json_data_supportive_example = {
        'uuid': 'patient-app-uuid-P1', 
        'Name': 'Patient Alpha', 
        'Age_year': '10', 'Age_month': '1', 'Sex': 'M', 'uhid': 'UHID-P1', 
        'Bed_Number': '', 
        'Diagnosis': 'General Malaise', 
        'Consultants': 'Dr. Whiskers',
        'each_entry_layout': { 
            'entry_sc1': {
                'title': 'Supportive care', 
                'subtitles': {
                    'subtitle_1': {
                        'content': 'Warm blanket and gentle petting', 
                        'rate': 'Continuous',
                        'volume': 'As tolerated'
                    }
                }
            }
        }, 
        'each_table_row_layout': { 
            'row_A1': {'row_header_name': 'Date', 'row_header_description': '2024-01-05'}, 
            'row_A2': {'row_header_name': 'Time', 'row_header_description': '01:00 PM'}
        }
    }
    print("\n\n--- Processing Patient 1, New Diagnosis 'General Malaise', with Supportive Care, Empty Bed ---")
    process_json_data(json_data_supportive_example)

    # Sixth run: Example with empty/None diagnosis, no Bed_Number field
    json_data_empty_diag_no_bed = {
        'uuid': 'patient-app-uuid-P3',
        'Name': 'Patient Gamma',
        'Age_year': '5', 'Age_month': '0', 'Sex': 'O', 'uhid': 'UHID-P3',
        'Diagnosis': None, 
        'Consultants': 'Dr. X',
        'each_table_row_layout': {
            'row_B1': {'row_header_name': 'Date', 'row_header_description': '2024-01-06'},
            'row_B2': {'row_header_name': 'Time', 'row_header_description': '02:00 PM'}
        }
    }
    print("\n\n--- Processing Patient 3, Empty Diagnosis, No Bed Number Field (should default to N/A for diagnosis, NULL for bed) ---")
    process_json_data(json_data_empty_diag_no_bed)

    json_data_whitespace_diag = {
        'uuid': 'patient-app-uuid-P4',
        'Name': 'Patient Delta',
        'Age_year': '7', 'Age_month': '0', 'Sex': 'F', 'uhid': 'UHID-P4',
        'Bed_Number': '303',
        'Diagnosis': '   ', 
        'Consultants': 'Dr. Y',
        'each_table_row_layout': {
            'row_C1': {'row_header_name': 'Date', 'row_header_description': '2024-01-07'},
            'row_C2': {'row_header_name': 'Time', 'row_header_description': '03:00 PM'}
        }
    }
    print("\n\n--- Processing Patient 4, Whitespace-only Diagnosis (should default to N/A) ---")
    process_json_data(json_data_whitespace_diag)

# END OF FILE external_database_handler.py
