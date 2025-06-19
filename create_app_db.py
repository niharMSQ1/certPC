import sqlite3
import os

DATABASE_NAME = "app.db"

def create_schema(conn):
    cursor = conn.cursor()

    # Drop tables if they exist (for idempotency during development)
    cursor.execute("DROP TABLE IF EXISTS control_standard_mapping")
    cursor.execute("DROP TABLE IF EXISTS controls")
    cursor.execute("DROP TABLE IF EXISTS standards")
    cursor.execute("DROP TABLE IF EXISTS policies")

    # Create policies table
    cursor.execute("""
    CREATE TABLE policies (
        id TEXT PRIMARY KEY,
        name TEXT,
        category TEXT,
        description TEXT
    )
    """)
    print("Table 'policies' created.")

    # Create controls table
    cursor.execute("""
    CREATE TABLE controls (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        policy_id TEXT,
        FOREIGN KEY (policy_id) REFERENCES policies(id)
    )
    """)
    print("Table 'controls' created.")

    # Create standards table
    cursor.execute("""
    CREATE TABLE standards (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT
    )
    """)
    print("Table 'standards' created.")

    # Create control_standard_mapping table
    cursor.execute("""
    CREATE TABLE control_standard_mapping (
        control_id TEXT,
        standard_id TEXT,
        PRIMARY KEY (control_id, standard_id),
        FOREIGN KEY (control_id) REFERENCES controls(id),
        FOREIGN KEY (standard_id) REFERENCES standards(id)
    )
    """)
    print("Table 'control_standard_mapping' created.")

    conn.commit()
    print("Database schema created successfully in app.db.")

def main():
    print("--- Script execution started ---")
    # Remove existing database file if it exists to ensure a fresh start
    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)
        print(f"Removed existing database: {DATABASE_NAME}")

    conn = sqlite3.connect(DATABASE_NAME)
    print(f"Connected to database: {DATABASE_NAME}")
    create_schema(conn)
    conn.close()
    print(f"Connection closed. Database '{DATABASE_NAME}' created and schema initialized.")
    print("--- Script execution finished ---")

if __name__ == "__main__":
    main()
