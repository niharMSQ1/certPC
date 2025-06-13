import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
import sqlite3

DATABASE_NAME = "compliance_database.sqlite"

# 2. Database Connection Function
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# 3. Dash App Initialization
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# 5. Data Querying for Policy List View
def get_policies_by_category():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT
        s.title as category,
        p.id as policy_id,
        p.title as policy_title,
        p.short_name as policy_short_name,
        p.description as policy_description
    FROM policies p
    JOIN section_policy_mappings spm ON p.id = spm.policy_id
    JOIN standard_sections s ON spm.standard_section_id = s.id
    ORDER BY category, policy_title;
    """
    cursor.execute(query)
    fetched_policies = cursor.fetchall()
    conn.close()

    policies_by_category = {}
    for policy in fetched_policies:
        category = policy["category"]
        if category not in policies_by_category:
            policies_by_category[category] = []
        policies_by_category[category].append(policy)
    return policies_by_category

# 6. Rendering Policy List View
def render_policy_view():
    policies_by_cat = get_policies_by_category()
    if not policies_by_cat:
        return html.P("No policies found or issues connecting to the database.")

    accordion_items = []
    for category, policies in policies_by_cat.items():
        policy_elements = []
        for policy in policies:
            policy_elements.append(
                html.Div([
                    html.H5(policy["policy_title"], className="mt-3"),
                    html.P(f"Short Name: {policy['policy_short_name']}"),
                    html.P(policy["policy_description"] if policy["policy_description"] else "No description available.")
                ], className="mb-2")
            )

        accordion_item = dbc.AccordionItem(
            policy_elements,
            title=category if category else "Uncategorized Policies"
        )
        accordion_items.append(accordion_item)

    return dbc.Accordion(accordion_items, always_open=True, class_name="mt-3")

# 4. Layout Definition
app.layout = dbc.Container([
    html.H1("Policy and Control Explorer", className="my-4"),
    dbc.Tabs(
        [
            dbc.Tab(label="Policies", tab_id="tab-policies"),
            dbc.Tab(label="Controls Mapping", tab_id="tab-controls"),
            dbc.Tab(label="Standards", tab_id="tab-standards"),
        ],
        id="tabs-main",
        active_tab="tab-policies", # Set default active tab
    ),
    html.Div(id="tab-content", className="mt-4")
], fluid=True)


# 7. Callback for Tab Switching
@app.callback(
    Output("tab-content", "children"),
    Input("tabs-main", "active_tab")
)
def switch_tab(active_tab):
    if active_tab == "tab-policies":
        return render_policy_view()
    elif active_tab == "tab-controls":
        return render_controls_mapping_view()
    elif active_tab == "tab-standards":
        return render_standards_tab_view() # Updated
    return html.P("Select a tab.")

# --- Data Querying Functions ---

# For Policy List View (already exists)

# For Controls Mapping View (already exists)
def get_controls_for_access_control_policy(policy_short_name='POL-2'): # Existing
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT DISTINCT
        c.id as control_id,
        c.short_name as control_short_name,
        c.name as control_name,
        c.description as control_description
    FROM controls c
    JOIN subsection_control_mappings scm ON c.id = scm.control_id
    JOIN standard_subsections ss ON scm.standard_subsection_id = ss.id
    JOIN standard_sections s_sec ON ss.standard_section_id = s_sec.id
    JOIN section_policy_mappings spm ON s_sec.id = spm.standard_section_id
    JOIN policies p ON spm.policy_id = p.id
    WHERE p.short_name = ?
    ORDER BY c.name;
    """
    cursor.execute(query, (policy_short_name,))
    controls = cursor.fetchall()
    conn.close()
    return controls

# Function to get a single control's details
def get_control_details(control_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, short_name, name, description FROM controls WHERE id = ?"
    cursor.execute(query, (control_id,))
    control = cursor.fetchone()
    conn.close()
    return control

# 1. Data Querying for Standards List
def get_all_standards():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM standards ORDER BY name")
    standards = cursor.fetchall()
    conn.close()
    return standards

# 2. Data Querying for Standard Details
def get_standard_details(standard_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get Standard Name
    cursor.execute("SELECT name FROM standards WHERE id = ?", (standard_id,))
    standard = cursor.fetchone()
    if not standard:
        conn.close()
        return None

    standard_details = {"id": standard_id, "name": standard["name"], "sections": []}

    # Get Sections for a Standard
    cursor.execute("""
        SELECT id, title, description, display_identifier
        FROM standard_sections
        WHERE standard_id = ?
        ORDER BY display_identifier, title
    """, (standard_id,))
    sections = cursor.fetchall()

    for sec in sections:
        section_data = {
            "id": sec["id"],
            "title": sec["title"],
            "description": sec["description"],
            "display_identifier": sec["display_identifier"],
            "policies": [],
            "subsections": []
        }

        # Get Policies for a Section
        cursor.execute("""
            SELECT p.id, p.title, p.short_name, p.description
            FROM policies p
            JOIN section_policy_mappings spm ON p.id = spm.policy_id
            WHERE spm.standard_section_id = ?
            ORDER BY p.title
        """, (sec["id"],))
        policies = cursor.fetchall()
        for pol in policies:
            section_data["policies"].append(dict(pol))

        # Get Subsections for a Section
        cursor.execute("""
            SELECT id, name, description, reference_id
            FROM standard_subsections
            WHERE standard_section_id = ?
            ORDER BY reference_id, name
        """, (sec["id"],))
        subsections = cursor.fetchall()

        for sub_sec in subsections:
            subsection_data = {
                "id": sub_sec["id"],
                "name": sub_sec["name"],
                "description": sub_sec["description"],
                "reference_id": sub_sec["reference_id"],
                "controls": []
            }

            # Get Controls for a Subsection
            cursor.execute("""
                SELECT c.id, c.name, c.short_name, c.description
                FROM controls c
                JOIN subsection_control_mappings scm ON c.id = scm.control_id
                WHERE scm.standard_subsection_id = ?
                ORDER BY c.name
            """, (sub_sec["id"],))
            controls = cursor.fetchall()
            for ctrl in controls:
                subsection_data["controls"].append(dict(ctrl))

            section_data["subsections"].append(subsection_data)
        standard_details["sections"].append(section_data)

    conn.close()
    return standard_details

# --- Rendering Functions ---

# For Policy List View (already exists)

# For Controls Mapping View
def render_controls_mapping_view(): # Existing, slight re-position for clarity
    controls = get_controls_for_access_control_policy(policy_short_name='POL-2')

    if not controls:
        return html.P("Access Control Policy (e.g., POL-2) not found or no controls mapped under it.")

    list_group_items = []
    for control in controls:
        item_text = f"{control['control_name']} ({control['control_short_name']})"
        list_group_items.append(
            dbc.ListGroupItem(
                item_text,
                id={'type': 'control-item', 'index': control['control_id']},
                action=True, # Makes it clickable
                className="control-list-item" # For potential styling
            )
        )

    return html.Div([
        html.H4("Controls Mapped to Access Control Policy (e.g., POL-2)", className="mt-4 mb-3"),
        dbc.Row([
            dbc.Col(dbc.ListGroup(list_group_items, flush=True), md=4),
            dbc.Col(html.Div(id='control-detail-output'), md=8)
        ])
    ])

# 3. Callback for Control Click
@app.callback(
    Output('control-detail-output', 'children'),
    Input({'type': 'control-item', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True # Important: do not run on page load
)
def display_control_details(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks): # Check if any item was clicked
        return dash.no_update # Or some default message like "Click a control to see details"

    # Get the ID of the clicked item
    triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
    # The ID is a string representation of a dictionary, e.g., '{"index":"C-123","type":"control-item"}'
    # We need to parse it to get the actual control ID.
    import json
    try:
        triggered_id_dict = json.loads(triggered_id_str)
        control_id = triggered_id_dict['index']
    except json.JSONDecodeError:
        return html.P("Error parsing control ID.", className="text-danger")


    control = get_control_details(control_id)

    if control:
        return dbc.Card([
            dbc.CardHeader(f"Details for: {control['name']} ({control['short_name']})"),
            dbc.CardBody([
                html.H5(control['name'], className="card-title"),
                html.H6(f"ID: {control['id']}", className="card-subtitle mb-2 text-muted"),
                html.H6(f"Short Name: {control['short_name']}", className="card-subtitle mb-2 text-muted"),
                html.P(control['description'] if control['description'] else "No description available.", className="card-text")
            ])
        ], className="mt-3 shadow-sm") # Added some styling
    else:
        return html.P(f"Control details not found for ID: {control_id}", className="text-warning")

# 3. Rendering Standards Tab (List and Detail Area)
def render_standards_tab_view():
    standards = get_all_standards()
    if not standards:
        return html.P("No standards found in the database.")

    list_group_items = [
        dbc.ListGroupItem(
            standard["name"],
            id={'type': 'standard-item', 'index': standard['id']},
            action=True
        ) for standard in standards
    ]

    return html.Div([
        html.H4("Available Standards", className="mt-4 mb-3"),
        dbc.Row([
            dbc.Col(dbc.ListGroup(list_group_items, flush=True), md=4, id="standard-list-col"),
            dbc.Col(html.Div(id='standard-detail-output', children=[html.P("Select a standard to see its details.")]), md=8, id="standard-detail-col")
        ])
    ])

# 4. Rendering Standard Detail View
def render_standard_detail_view(standard_id):
    details = get_standard_details(standard_id)
    if not details:
        return html.P(f"Details not found for Standard ID: {standard_id}", className="text-warning")

    standard_layout = [html.H2(details['name'], className="mb-3")]

    for section in details.get('sections', []):
        section_title = section.get('display_identifier', '') + " " + section.get('title', 'Unnamed Section')
        section_content = [html.H4(section_title, className="mt-4")]
        if section.get('description'):
            section_content.append(dcc.Markdown(section['description']))

        # Policies for the section
        if section.get('policies'):
            section_content.append(html.H5("Mapped Policies:", className="mt-3 text-primary"))
            policy_list_items = []
            for policy in section['policies']:
                policy_list_items.append(html.Li(f"{policy['title']} ({policy['short_name']})"))
            section_content.append(html.Ul(policy_list_items))

        # Subsections
        for subsection in section.get('subsections', []):
            subsection_title = subsection.get('reference_id', '') + " " + subsection.get('name', 'Unnamed Subsection')
            section_content.append(html.H5(subsection_title, className="mt-3"))
            if subsection.get('description'):
                section_content.append(dcc.Markdown(subsection['description']))

            # Controls for the subsection
            if subsection.get('controls'):
                section_content.append(html.H6("Mapped Controls:", className="mt-2 text-secondary"))
                control_list_items = []
                for control in subsection['controls']:
                    control_list_items.append(html.Li(f"{control['name']} ({control['short_name']})"))
                section_content.append(html.Ul(control_list_items))

        standard_layout.append(dbc.Card(dbc.CardBody(section_content), className="mb-3 shadow-sm"))

    return html.Div(standard_layout)


# --- Callbacks ---

# For Policy List View (already exists - main tab callback)

# For Controls Mapping View (already exists - main tab callback and control click)

# 5. Callback for Standard Click
@app.callback(
    Output('standard-detail-output', 'children'),
    Input({'type': 'standard-item', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def display_standard_details(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(n_clicks):
        return dash.no_update

    triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
    import json
    try:
        triggered_id_dict = json.loads(triggered_id_str)
        standard_id = triggered_id_dict['index']
    except json.JSONDecodeError:
        return html.P("Error parsing standard ID.", className="text-danger")

    return render_standard_detail_view(standard_id)


# 8. Run Server (no change)
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8050)
