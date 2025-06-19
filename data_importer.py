import sqlite3
import json
import glob
import os

DB_NAME = 'compliance_data.db' # Changed DB name

# Step 0: Remove database if it exists for a clean run
# if os.path.exists(DB_NAME):
#     os.remove(DB_NAME)
#     print(f"Removed existing database {DB_NAME}.")

# Step 1: Define schema and create database + tables
def create_schema_and_db():
    # Moved OS remove here, to be after initial script load and within a function
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"Removed existing database {DB_NAME} from within create_schema_and_db.")

    print(f"Attempting to create database: {DB_NAME}")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("Database connected.")

    # Policies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS policies (
        id TEXT PRIMARY KEY,
        name TEXT,
        category TEXT,
        description TEXT
    )
    ''')
    print("Policies table schema created.")

    # Standards table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS standards (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT
    )
    ''')
    print("Standards table schema created.")

    # Controls table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS controls (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        standard_id TEXT,
        FOREIGN KEY (standard_id) REFERENCES standards(id)
    )
    ''')
    print("Controls table schema created.")

    # Policy-Control Mapping table (Many-to-Many)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS policy_control_mapping (
        policy_id TEXT,
        control_id TEXT,
        PRIMARY KEY (policy_id, control_id),
        FOREIGN KEY (policy_id) REFERENCES policies(id),
        FOREIGN KEY (control_id) REFERENCES controls(id)
    )
    ''')
    print("Policy-Control mapping table schema created.")

    conn.commit()
    conn.close()
    print("Database and tables created/verified.")

# Step 2: Load data from JSON files
def load_data():
    print(f"Attempting to connect to {DB_NAME} for data loading.")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("Database connected for data loading.")

    json_files = glob.glob('sections_*.json')
    if not json_files:
        print("No section JSON files found (sections_*.json).")
        conn.close()
        return

    print(f"Found JSON files: {json_files}")

    for file_path in json_files:
        print(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f: # Added encoding
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {file_path}: {e}")
            continue
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            continue

        for section in data:
            policy_category = section.get('title')
            section_policies_ids = []

            if section.get('programPolicyMapping'):
                for policy_data in section['programPolicyMapping']:
                    policy_id = policy_data.get('id')
                    if not policy_id:
                        print(f"Skipping policy with no id in {file_path}, section {policy_category}")
                        continue
                    section_policies_ids.append(policy_id)
                    try:
                        cursor.execute("INSERT OR IGNORE INTO policies (id, name, category, description) VALUES (?, ?, ?, ?)",
                                       (policy_id, policy_data.get('title'), policy_category, policy_data.get('description')))
                    except Exception as e:
                        print(f"Error inserting policy ID {policy_id}: {e}")

            if section.get('subsections'):
                for standard_data in section['subsections']: # In JSON, these are 'subsections', script calls them 'standards'
                    standard_id = standard_data.get('id') # This is subsection_id from JSON
                    if not standard_id:
                        print(f"Skipping standard (JSON subsection) with no id in {file_path}, section {policy_category}")
                        continue
                    try:
                        cursor.execute("INSERT OR IGNORE INTO standards (id, name, description) VALUES (?, ?, ?)",
                                       (standard_id, standard_data.get('name'), standard_data.get('description')))
                    except Exception as e:
                        print(f"Error inserting standard ID {standard_id}: {e}")

                    if standard_data.get('programControlMapping'):
                        for control_data in standard_data['programControlMapping']:
                            control_id = control_data.get('id')
                            if not control_id:
                                print(f"Skipping control with no id in {file_path}, standard (JSON subsection) {standard_id}")
                                continue
                            try:
                                # The standard_id FK in controls table refers to the id of a 'subsection' from JSON
                                cursor.execute("INSERT OR IGNORE INTO controls (id, name, description, standard_id) VALUES (?, ?, ?, ?)",
                                               (control_id, control_data.get('name'), control_data.get('description'), standard_id))

                                for pol_id in section_policies_ids:
                                    try:
                                        cursor.execute("INSERT OR IGNORE INTO policy_control_mapping (policy_id, control_id) VALUES (?, ?)",
                                                       (pol_id, control_id))
                                    except Exception as e:
                                        print(f"Error inserting policy_control_mapping for policy {pol_id}, control {control_id}: {e}")
                            except Exception as e:
                                print(f"Error inserting control ID {control_id}: {e}")

    conn.commit()
    conn.close()
    print("Data loading complete.")

if __name__ == '__main__':
    print("Starting script execution.")
    create_schema_and_db()
    load_data()

    print("Verifying data insertion...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    policies_count = cursor.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    standards_count = cursor.execute("SELECT COUNT(*) FROM standards").fetchone()[0]
    controls_count = cursor.execute("SELECT COUNT(*) FROM controls").fetchone()[0]
    mappings_count = cursor.execute("SELECT COUNT(*) FROM policy_control_mapping").fetchone()[0]
    conn.close()

    print(f"Policies count: {policies_count}")
    print(f"Standards count: {standards_count}")
    print(f"Controls count: {controls_count}")
    print(f"Policy-Control Mappings count: {mappings_count}")

    if policies_count > 0 and standards_count > 0 and controls_count > 0 and mappings_count > 0 :
        print("Data verification successful: Tables are populated.")
    else:
        print("Data verification failed: Some tables might be empty or not populated as expected.")
        # It's possible some sections don't have all types of data, so this isn't a strict failure, but good for logging.

    print("Script finished.")
