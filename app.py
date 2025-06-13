import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context
import sqlite3
import json # Added for parsing callback context if necessary

DATABASE_NAME = "compliance_database.sqlite"

# 2. Database Connection Function (no change)
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- Data Querying Functions ---

# For Policy List View (already exists)
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

# NEW: Function to get all policies for the dropdown
def get_all_policies_for_dropdown():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetching title and id, sorting by title for user-friendliness
    query = "SELECT id, title, short_name FROM policies ORDER BY title"
    cursor.execute(query)
    policies = cursor.fetchall()
    conn.close()
    # Format for dcc.Dropdown: list of dicts {'label': policy_name, 'value': policy_id}
    return [{'label': f"{p['title']} ({p['short_name']})", 'value': p['id']} for p in policies]

# MODIFIED: Function to get controls for a selected policy ID
def get_controls_for_policy(policy_id):
    if not policy_id:
        return []
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
    WHERE p.id = ?  -- Changed from p.short_name to p.id
    ORDER BY c.name;
    """
    cursor.execute(query, (policy_id,)) # Pass policy_id
    controls = cursor.fetchall()
    conn.close()
    return controls

# Function to get a single control's details (no change)
def get_control_details(control_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, short_name, name, description FROM controls WHERE id = ?"
    cursor.execute(query, (control_id,))
    control = cursor.fetchone()
    conn.close()
    return control

# For Standards View (no change to these functions)
def get_all_standards():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM standards ORDER BY name")
    standards = cursor.fetchall()
    conn.close()
    return standards

def get_standard_details(standard_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM standards WHERE id = ?", (standard_id,))
    standard = cursor.fetchone()
    if not standard:
        conn.close(); return None
    standard_details = {"id": standard_id, "name": standard["name"], "sections": []}
    cursor.execute("SELECT id, title, description, display_identifier FROM standard_sections WHERE standard_id = ? ORDER BY display_identifier, title", (standard_id,))
    sections = cursor.fetchall()
    for sec in sections:
        section_data = {"id": sec["id"], "title": sec["title"], "description": sec["description"], "display_identifier": sec["display_identifier"], "policies": [], "subsections": []}
        cursor.execute("SELECT p.id, p.title, p.short_name, p.description FROM policies p JOIN section_policy_mappings spm ON p.id = spm.policy_id WHERE spm.standard_section_id = ? ORDER BY p.title", (sec["id"],))
        policies = cursor.fetchall(); section_data["policies"] = [dict(pol) for pol in policies]
        cursor.execute("SELECT id, name, description, reference_id FROM standard_subsections WHERE standard_section_id = ? ORDER BY reference_id, name", (sec["id"],))
        subsections = cursor.fetchall()
        for sub_sec in subsections:
            subsection_data = {"id": sub_sec["id"], "name": sub_sec["name"], "description": sub_sec["description"], "reference_id": sub_sec["reference_id"], "controls": []}
            cursor.execute("SELECT c.id, c.name, c.short_name, c.description FROM controls c JOIN subsection_control_mappings scm ON c.id = scm.control_id WHERE scm.standard_subsection_id = ? ORDER BY c.name", (sub_sec["id"],))
            controls = cursor.fetchall(); subsection_data["controls"] = [dict(ctrl) for ctrl in controls]
            section_data["subsections"].append(subsection_data)
        standard_details["sections"].append(section_data)
    conn.close()
    return standard_details

# --- Dash App Initialization ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

# --- Rendering Functions ---

# For Policy List View (no change)
def render_policy_view():
    policies_by_cat = get_policies_by_category()
    if not policies_by_cat: return html.P("No policies found.")
    accordion_items = []
    for category, policies in policies_by_cat.items():
        policy_elements = [html.Div([html.H5(p["policy_title"], className="mt-3"), html.P(f"Short Name: {p['policy_short_name']}"), html.P(p["policy_description"] if p["policy_description"] else "No description.")], className="mb-2") for p in policies]
        accordion_items.append(dbc.AccordionItem(policy_elements, title=category if category else "Uncategorized"))
    return dbc.Accordion(accordion_items, always_open=True, class_name="mt-3")

# MODIFIED: For Controls Mapping View
def render_controls_mapping_view():
    all_policies = get_all_policies_for_dropdown()

    if not all_policies:
        return html.P("No policies available to select.", className="text-warning mt-4")

    return html.Div([
        html.H4("Select a Policy to View Mapped Controls", className="mt-4 mb-3"),
        dcc.Dropdown(
            id='policy-dropdown',
            options=all_policies,
            value=all_policies[0]['value'] if all_policies else None, # Default to first policy or None
            clearable=False,
            className="mb-3"
        ),
        dbc.Row([
            dbc.Col(html.Div(id='controls-list-container'), md=4), # Container for the list group
            dbc.Col(html.Div(id='control-detail-output'), md=8)
        ])
    ])

# For Standards View (no change)
def render_standards_tab_view():
    standards = get_all_standards()
    if not standards: return html.P("No standards found.")
    list_group_items = [dbc.ListGroupItem(s["name"], id={'type': 'standard-item', 'index': s['id']}, action=True) for s in standards]
    return html.Div([html.H4("Available Standards", className="mt-4 mb-3"), dbc.Row([dbc.Col(dbc.ListGroup(list_group_items, flush=True), md=4), dbc.Col(html.Div(id='standard-detail-output', children=[html.P("Select a standard to see its details.")]), md=8)])])

def render_standard_detail_view(standard_id): # No change
    details = get_standard_details(standard_id)
    if not details: return html.P(f"Details not found for Standard ID: {standard_id}", className="text-warning")
    standard_layout = [html.H2(details['name'], className="mb-3")]
    for section in details.get('sections', []):
        section_title = section.get('display_identifier', '') + " " + section.get('title', 'Unnamed Section')
        section_content = [html.H4(section_title, className="mt-4")]
        if section.get('description'): section_content.append(dcc.Markdown(section['description']))
        if section.get('policies'):
            section_content.append(html.H5("Mapped Policies:", className="mt-3 text-primary"))
            section_content.append(html.Ul([html.Li(f"{p['title']} ({p['short_name']})") for p in section['policies']]))
        for subsection in section.get('subsections', []):
            subsection_title = subsection.get('reference_id', '') + " " + subsection.get('name', 'Unnamed Subsection')
            section_content.append(html.H5(subsection_title, className="mt-3"))
            if subsection.get('description'): section_content.append(dcc.Markdown(subsection['description']))
            if subsection.get('controls'):
                section_content.append(html.H6("Mapped Controls:", className="mt-2 text-secondary"))
                section_content.append(html.Ul([html.Li(f"{c['name']} ({c['short_name']})") for c in subsection['controls']]))
        standard_layout.append(dbc.Card(dbc.CardBody(section_content), className="mb-3 shadow-sm"))
    return html.Div(standard_layout)

# --- Layout Definition (no change) ---
app.layout = dbc.Container([
    html.H1("Policy and Control Explorer", className="my-4"),
    dbc.Tabs([
        dbc.Tab(label="Policies", tab_id="tab-policies"),
        dbc.Tab(label="Controls Mapping", tab_id="tab-controls"),
        dbc.Tab(label="Standards", tab_id="tab-standards"),
    ], id="tabs-main", active_tab="tab-policies"),
    html.Div(id="tab-content", className="mt-4")
], fluid=True)

# --- Callbacks ---

# Main Tab Switching Callback (no change)
@app.callback(Output("tab-content", "children"), Input("tabs-main", "active_tab"))
def switch_tab(active_tab):
    if active_tab == "tab-policies": return render_policy_view()
    if active_tab == "tab-controls": return render_controls_mapping_view()
    if active_tab == "tab-standards": return render_standards_tab_view()
    return html.P("Select a tab.")

# NEW: Callback to update controls list based on policy dropdown
@app.callback(
    Output('controls-list-container', 'children'),
    Input('policy-dropdown', 'value')
)
def update_controls_list(selected_policy_id):
    if not selected_policy_id:
        # This can happen if the dropdown is cleared or no default value is set and no policy is selected.
        # Or if all_policies was empty and value was None.
        return html.P("Please select a policy to see mapped controls.", className="text-info mt-3")

    controls = get_controls_for_policy(selected_policy_id)

    if not controls:
        return html.P("No controls found for the selected policy.", className="text-info mt-3")

    list_group_items = [
        dbc.ListGroupItem(
            f"{control['control_name']} ({control['control_short_name']})",
            id={'type': 'control-item', 'index': control['control_id']},
            action=True,
            className="control-list-item"
        ) for control in controls
    ]
    return dbc.ListGroup(list_group_items, flush=True)

# MODIFIED: Callback for Control Click (ID parsing logic improved)
@app.callback(
    Output('control-detail-output', 'children'),
    Input({'type': 'control-item', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def display_control_details(n_clicks):
    ctx = callback_context # Use callback_context directly
    if not ctx.triggered or not any(n_clicks): # check if any n_clicks is > 0 or non-None
        return dash.no_update # Or some default message like "Click a control to see details"

    triggered_input = ctx.triggered[0]
    prop_id_str = triggered_input['prop_id']

    # prop_id_str is like '{"index":"ID_STRING","type":"control-item"}.n_clicks'
    # We need to extract the JSON part.
    # Ensure splitting results in at least one part before accessing [0]
    json_parts = prop_id_str.split('.n_clicks', 1)
    if not json_parts:
        print(f"Error processing prop_id_str: {prop_id_str}")
        return html.P("Error processing callback trigger.", className="text-danger")
    json_str = json_parts[0]

    try:
        triggered_id_dict = json.loads(json_str)
        control_id = triggered_id_dict['index']
    except json.JSONDecodeError:
        print(f"Error parsing control ID from: {json_str}")
        return html.P("Error parsing control ID.", className="text-danger")
    except KeyError:
        print(f"Key 'index' not found in parsed ID: {triggered_id_dict}")
        return html.P("Control ID not found in callback context.", className="text-danger")


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
        ], className="mt-3 shadow-sm")
    else:
        return html.P(f"Control details not found for ID: {control_id}", className="text-warning")

# Callback for Standard Click (ID parsing logic improved)
@app.callback(
    Output('standard-detail-output', 'children'),
    Input({'type': 'standard-item', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def display_standard_details(n_clicks):
    ctx = callback_context # Use callback_context directly
    if not ctx.triggered or not any(n_clicks):
        return dash.no_update

    triggered_input = ctx.triggered[0]
    prop_id_str = triggered_input['prop_id']

    json_parts = prop_id_str.split('.n_clicks', 1)
    if not json_parts:
        print(f"Error processing prop_id_str for standard: {prop_id_str}")
        return html.P("Error processing callback trigger for standard.", className="text-danger")
    json_str = json_parts[0]

    try:
        triggered_id_dict = json.loads(json_str)
        standard_id = triggered_id_dict['index']
    except json.JSONDecodeError:
        print(f"Error parsing standard ID from: {json_str}")
        return html.P("Error parsing standard ID.", className="text-danger")
    except KeyError:
        print(f"Key 'index' not found in parsed ID for standard: {triggered_id_dict}")
        return html.P("Standard ID not found in callback context.", className="text-danger")

    return render_standard_detail_view(standard_id)

# Run Server (no change)
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8050)
