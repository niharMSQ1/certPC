# Compliance Data Explorer

## Description
The Compliance Data Explorer is a web application built with Python and Dash. It allows users to navigate and explore compliance data, including policies, controls, and standards, which are initially populated from JSON data sources into an SQLite database. The application provides a user-friendly interface to view these entities and their relationships.

## Prerequisites
*   Python 3.7+
*   pip (Python package installer)

## Setup Instructions

1.  **Clone the Repository / Download Files:**
    Ensure you have all project files (`data_importer.py`, `app.py`, the `assets` folder with `custom.css`, and the necessary JSON data files) in a local directory.

2.  **Create a Virtual Environment (Recommended):**
    Open your terminal or command prompt in the project's root directory and run:
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    *   On macOS and Linux:
        ```bash
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    With your virtual environment active, install the required Python packages:
    ```bash
    pip install dash dash-bootstrap-components pandas
    ```

## Running the Application

1.  **Populate the Database:**
    Before running the web application for the first time (or if the source JSON data has changed), you need to populate the SQLite database. Run the data importer script from the project's root directory:
    ```bash
    python data_importer.py
    ```
    This will create a `compliance_database.sqlite` file in the root directory.

2.  **Run the Dash App:**
    Once the database is populated, start the Dash application:
    ```bash
    python app.py
    ```

3.  **Access the Application:**
    Open a web browser and navigate to `http://127.0.0.1:8050/` (or the address shown in your terminal, typically `http://0.0.0.0:8050/` which can be accessed via `127.0.0.1` or `localhost`).

## Features

The application is organized into three main tabs:

*   **Policies Tab:**
    Displays a list of all policies, categorized by the standard sections they are mapped to. Each category can be expanded (using an accordion view) to show individual policies with their title, short name, and description.

*   **Controls Mapping Tab:**
    Shows controls that are mapped to a specific policy (currently hardcoded to "Access Control Policy", identified by `POL-2`). Controls are listed, and clicking on a control displays its detailed information (name, short name, description) in a card view.

*   **Standards Tab:**
    Lists all available standards from the database. Clicking on a standard name reveals a detailed breakdown, including:
    *   The standard's name.
    *   Sections within the standard, along with their titles and descriptions.
    *   Policies mapped to each section.
    *   Subsections within each section, with their names and descriptions.
    *   Controls mapped to each subsection.
    This detailed view is presented using nested cards and lists for clarity.

The application uses Dash Bootstrap Components for layout and styling, enhanced by custom CSS for improved readability.
