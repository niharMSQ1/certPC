import sqlite3
import json
import os

DATABASE_NAME = "compliance_database.sqlite"

def create_schema(conn):
    cursor = conn.cursor()

    # Drop tables if they exist (for idempotency during development)
    cursor.execute("DROP TABLE IF EXISTS subsection_control_mappings")
    cursor.execute("DROP TABLE IF EXISTS section_policy_mappings")
    cursor.execute("DROP TABLE IF EXISTS standard_subsections")
    cursor.execute("DROP TABLE IF EXISTS standard_sections")
    cursor.execute("DROP TABLE IF EXISTS controls")
    cursor.execute("DROP TABLE IF EXISTS policies")
    cursor.execute("DROP TABLE IF EXISTS standards")

    # Create standards table
    cursor.execute("""
    CREATE TABLE standards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        source_file TEXT
    )
    """)

    # Create policies table
    cursor.execute("""
    CREATE TABLE policies (
        id TEXT PRIMARY KEY,
        short_name TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        UNIQUE(short_name, title)
    )
    """)

    # Create controls table
    cursor.execute("""
    CREATE TABLE controls (
        id TEXT PRIMARY KEY,
        short_name TEXT NOT NULL,
        custom_short_name TEXT,
        name TEXT NOT NULL,
        description TEXT,
        UNIQUE(short_name, name)
    )
    """)

    # Create standard_sections table
    cursor.execute("""
    CREATE TABLE standard_sections (
        id TEXT PRIMARY KEY,
        standard_id INTEGER,
        reference_id TEXT,
        display_identifier TEXT,
        title TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY (standard_id) REFERENCES standards(id)
    )
    """)

    # Create standard_subsections table
    cursor.execute("""
    CREATE TABLE standard_subsections (
        id TEXT PRIMARY KEY,
        standard_section_id TEXT,
        reference_id TEXT,
        name TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY (standard_section_id) REFERENCES standard_sections(id)
    )
    """)

    # Create section_policy_mappings table
    cursor.execute("""
    CREATE TABLE section_policy_mappings (
        standard_section_id TEXT,
        policy_id TEXT,
        PRIMARY KEY (standard_section_id, policy_id),
        FOREIGN KEY (standard_section_id) REFERENCES standard_sections(id),
        FOREIGN KEY (policy_id) REFERENCES policies(id)
    )
    """)

    # Create subsection_control_mappings table
    cursor.execute("""
    CREATE TABLE subsection_control_mappings (
        standard_subsection_id TEXT,
        control_id TEXT,
        PRIMARY KEY (standard_subsection_id, control_id),
        FOREIGN KEY (standard_subsection_id) REFERENCES standard_subsections(id),
        FOREIGN KEY (control_id) REFERENCES controls(id)
    )
    """)

    conn.commit()
    print("Database schema created successfully.")

def main():
    # Remove existing database file if it exists to ensure a fresh start
    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)
        print(f"Removed existing database: {DATABASE_NAME}")

    conn = sqlite3.connect(DATABASE_NAME)
    create_schema(conn)
    parse_raw_cert_links(conn)
    process_section_files(conn) # New function call
    conn.close()
    print(f"Database '{DATABASE_NAME}' populated successfully.")

def parse_raw_cert_links(conn):
    cursor = conn.cursor()
    try:
        with open("raw_cert_links.json", 'r') as f:
            cert_links = json.load(f)
    except FileNotFoundError:
        print("Error: raw_cert_links.json not found.")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode raw_cert_links.json.")
        return

    standards_data = []
    for item in cert_links:
        url = item.get("url")
        if url:
            # Extract standard name from URL (e.g., last part of path)
            try:
                name_part = url.split('/')[-1]
                # Further clean up common extensions or query params if necessary
                name_part = name_part.split('?')[0].split('#')[0]
                if not name_part: # If URL ends with /, take the second to last part
                    name_part = url.split('/')[-2]
                standards_data.append((name_part, "raw_cert_links.json"))
            except IndexError:
                print(f"Warning: Could not derive standard name from URL: {url}")
                continue # Skip if name cannot be derived

    if standards_data:
        try:
            cursor.executemany("INSERT INTO standards (name, source_file) VALUES (?, ?)", standards_data)
            conn.commit()
            print(f"Inserted {len(standards_data)} standards from raw_cert_links.json")
        except sqlite3.IntegrityError as e:
            # This can happen if the script is run multiple times without clearing the DB
            # or if raw_cert_links.json contains URLs that resolve to the same name.
            print(f"Warning: {e}. Some standards might already exist or have name conflicts.")
        except Exception as e:
            print(f"An unexpected error occurred during standard insertion: {e}")
    else:
        print("No standards data to insert from raw_cert_links.json")

def process_section_files(conn):
    cursor = conn.cursor()

    # 1. Fetch standard IDs from the database
    cursor.execute("SELECT id, name FROM standards ORDER BY id")
    db_standards = cursor.fetchall()

    if not db_standards:
        print("No standards found in the database. Cannot process section files.")
        return

    # 2. Define the list of section files to process
    section_files = [
        "sections_01.json", "sections_02.json", "sections_03.json",
        "sections_07.json", "sections_15.json"
    ]

    # 3. Create a mapping (heuristic: ordered mapping)
    # Ensure we don't try to map more files than available standards
    num_files_to_map = min(len(section_files), len(db_standards))

    standard_file_map = {}
    for i in range(num_files_to_map):
        standard_id = db_standards[i][0]
        standard_name = db_standards[i][1] # For logging/debugging
        json_file = section_files[i]
        standard_file_map[json_file] = standard_id
        print(f"Mapping: Standard ID {standard_id} (Name: {standard_name}) -> {json_file}")

    # Iterate through mapped section files
    for json_file_name, standard_id in standard_file_map.items():
        print(f"\nProcessing {json_file_name} for standard ID {standard_id}...")
        try:
            with open(json_file_name, 'r') as f:
                sections_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {json_file_name} not found.")
            continue
        except json.JSONDecodeError:
            print(f"Error: Could not decode {json_file_name}.")
            continue

        # Update source_file for the standard
        try:
            cursor.execute("UPDATE standards SET source_file = ? WHERE id = ?", (json_file_name, standard_id))
            conn.commit()
            print(f"Updated source_file for standard ID {standard_id} to {json_file_name}")
        except sqlite3.Error as e:
            print(f"Error updating source_file for standard ID {standard_id}: {e}")
            conn.rollback() # Rollback if this update fails
            continue # Skip this file if we can't update the standard

        for section in sections_data:
            section_id = section.get('id')
            if not section_id:
                print(f"Skipping section in {json_file_name} due to missing 'id'. Data: {section}")
                continue

            # Insert standard_section
            try:
                cursor.execute("""
                    INSERT INTO standard_sections (id, standard_id, reference_id, display_identifier, title, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    section_id,
                    standard_id,
                    section.get('reference_id'),
                    section.get('display_identifier'),
                    section.get('title'),
                    section.get('description')
                ))
            except sqlite3.IntegrityError as e:
                print(f"Error inserting section {section_id} from {json_file_name}: {e}. It might already exist.")
                # If section already exists, we might want to continue to process its policies/subsections
            except sqlite3.Error as e:
                print(f"SQLite error inserting section {section_id} from {json_file_name}: {e}")
                conn.rollback()
                continue # Skip to next section in this file

            # Process policies for this section
            for policy in section.get('programPolicyMapping', []):
                policy_id = policy.get('id')
                if not policy_id:
                    print(f"Skipping policy in section {section_id} ({json_file_name}) due to missing 'id'. Data: {policy}")
                    continue

                # Insert or ignore policy
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO policies (id, short_name, title, description)
                        VALUES (?, ?, ?, ?)
                    """, (
                        policy_id,
                        policy.get('short_name', f"Policy {policy_id}"), # Ensure short_name is not null
                        policy.get('title', f"Title for {policy_id}"),    # Ensure title is not null
                        policy.get('description')
                    ))
                except sqlite3.Error as e:
                    print(f"Error inserting policy {policy_id} for section {section_id}: {e}")
                    conn.rollback()
                    continue # Skip to next policy

                # Insert section_policy_mapping
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO section_policy_mappings (standard_section_id, policy_id)
                        VALUES (?, ?)
                    """, (section_id, policy_id))
                except sqlite3.IntegrityError as e: # Handles cases where mapping might already exist
                    print(f"Warning: Mapping for section {section_id} and policy {policy_id} already exists or foreign key constraint failed: {e}")
                except sqlite3.Error as e:
                    print(f"Error inserting mapping for section {section_id} and policy {policy_id}: {e}")
                    conn.rollback()
                    # Decide if we should stop processing this section or file

            # Process subsections for this section
            for subsection in section.get('subsections', []):
                subsection_id = subsection.get('id')
                if not subsection_id:
                    print(f"Skipping subsection in section {section_id} ({json_file_name}) due to missing 'id'. Data: {subsection}")
                    continue

                # Insert standard_subsection
                try:
                    cursor.execute("""
                        INSERT INTO standard_subsections (id, standard_section_id, reference_id, name, description)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        subsection_id,
                        section_id, # Link to parent section
                        subsection.get('reference_id'),
                        subsection.get('name', f"Subsection {subsection_id}"), # Ensure name is not null
                        subsection.get('description')
                    ))
                except sqlite3.IntegrityError as e:
                    print(f"Error inserting subsection {subsection_id} for section {section_id}: {e}. It might already exist.")
                except sqlite3.Error as e:
                    print(f"SQLite error inserting subsection {subsection_id} for section {section_id}: {e}")
                    conn.rollback()
                    continue # Skip to next subsection

                # Process controls for this subsection
                for control in subsection.get('programControlMapping', []):
                    control_id = control.get('id')
                    if not control_id:
                        print(f"Skipping control in subsection {subsection_id} ({json_file_name}) due to missing 'id'. Data: {control}")
                        continue

                    # Insert or ignore control
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO controls (id, short_name, custom_short_name, name, description)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            control_id,
                            control.get('short_name', f"Control {control_id}"), # Ensure short_name
                            control.get('custom_short_name'),
                            control.get('name', f"Name for {control_id}"),       # Ensure name
                            control.get('description')
                        ))
                    except sqlite3.Error as e:
                        print(f"Error inserting control {control_id} for subsection {subsection_id}: {e}")
                        conn.rollback()
                        continue # Skip to next control

                    # Insert subsection_control_mapping
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO subsection_control_mappings (standard_subsection_id, control_id)
                            VALUES (?, ?)
                        """, (subsection_id, control_id))
                    except sqlite3.IntegrityError as e:
                         print(f"Warning: Mapping for subsection {subsection_id} and control {control_id} already exists or foreign key constraint failed: {e}")
                    except sqlite3.Error as e:
                        print(f"Error inserting mapping for subsection {subsection_id} and control {control_id}: {e}")
                        conn.rollback()

        conn.commit() # Commit changes for the current JSON file

if __name__ == "__main__":
    main()
