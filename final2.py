# ---------------------------------------------------------
# FastAPI Excel Analyzer with Admin Panel for Alias Management
# ---------------------------------------------------------
# pip install fastapi uvicorn pandas openpyxl python-multipart pycountry phonenumbers pgeocode

from fastapi import FastAPI, UploadFile, Form, Cookie
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
import pandas as pd
import io
import json
import os
import phonenumbers
import pycountry
import pgeocode
import zipcodes
from typing import Union

app = FastAPI()

# Admin credentials
ADMIN_USERNAME = "admin@spectrasolns.com"
ADMIN_PASSWORD = "admin1234"

# Aliases file
ALIASES_FILE = "column_aliases.json"

uploaded_df = None
uploaded_filename = None
last_filtered_df = None
column_analysis = {}
detected_types = {}

# Default aliases
DEFAULT_ALIASES = {
    "date": ["date", "order_date", "dt", "datetime", "timestamp"],
    "phone_number": ["phone", "phone_number", "mobile", "contact", "tel"],
    "country_name": ["country", "country_name", "nation"],
    "country_code": ["country_code", "cc", "country_cd"],
    "region_category": ["region", "region_category", "state", "province", "subdivision"],  # ← ADD THIS LINE
    "zip_code": ["zip", "zip_code", "zipcode"],
    "postal_code": ["postal", "postal_code", "postcode"],
    "currency_code": ["currency", "currency_code", "curr"],
    "numerical": ["amount", "price", "value", "cost", "number", "qty", "quantity"],
}


def load_aliases():
    """Load aliases from JSON file or return defaults"""
    if os.path.exists(ALIASES_FILE):
        with open(ALIASES_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_ALIASES.copy()


def save_aliases(aliases):
    """Save aliases to JSON file"""
    with open(ALIASES_FILE, 'w') as f:
        json.dump(aliases, f, indent=2)


def safe_str(x):
    if pd.isna(x):
        return ""
    if isinstance(x, (pd.Timestamp, pd.DatetimeTZDtype)) or hasattr(x, 'date'):
        try:
            return str(x.date())
        except:
            pass
    return str(x)


def is_valid_phone(num):
    try:
        if num is None or str(num).strip() == "":
            return False
        parsed = phonenumbers.parse(str(num), None)
        return phonenumbers.is_valid_number(parsed)
    except:
        return False


def is_valid_country_name(name):
    try:
        if name is None or str(name).strip() == "":
            return False
        val = str(name).strip()
        if pycountry.countries.get(name=val):
            return True
        for c in pycountry.countries:
            if val.lower() == c.name.lower():
                return True
            if hasattr(c, 'official_name') and val.lower() == c.official_name.lower():
                return True
        return False
    except:
        return False


def is_valid_country_code(code):
    try:
        if code is None or str(code).strip() == "":
            return False
        return pycountry.countries.get(alpha_2=str(code).strip().upper()) is not None
    except:
        return False


def is_valid_currency(code):
    try:
        if code is None or str(code).strip() == "":
            return False
        return pycountry.currencies.get(alpha_3=str(code).strip().upper()) is not None
    except:
        return False


def is_valid_postal(country_code, postal_code):
    try:
        if postal_code is None or str(postal_code).strip() == "":
            return False
        nomi = pgeocode.Nominatim(country_code)
        loc = nomi.query_postal_code(str(postal_code))
        return not pd.isna(loc.get('country_code'))
    except:
        return False


def is_valid_zip(zipcode):
    """Safe wrapper for zipcodes.is_real() with error handling"""
    try:
        if zipcode is None or str(zipcode).strip() == "":
            return False
        zip_str = str(zipcode).strip()
        # Basic format check before calling zipcodes library
        if not zip_str.replace("-", "").isdigit():
            return False
        if len(zip_str.replace("-", "")) not in [5, 9]:
            return False
        return zipcodes.is_real(zip_str)
    except:
        return False

def is_valid_state_code(country_code, subdivision_code):
    """
    Checks if a subdivision code is valid for a given country.
    Simply checks if pycountry returns something (not None).
    """
    try:
        subdivision = pycountry.subdivisions.get(code=subdivision_code)
        # If we got a subdivision object (not None), it's valid
        if subdivision is not None:
            # Double-check it belongs to the correct country
            return subdivision.country_code == country_code
        return False
    except:
        return False

def detect_column_type(column_name: str):
    """Detect column type based on aliases - with specificity priority"""
    aliases = load_aliases()
    col_name_lower = column_name.lower().strip()

    # Sort each alias list by length (longest first) for better matching
    best_match = None
    best_match_length = 0

    for col_type, alias_list in aliases.items():
        for alias in alias_list:
            alias_lower = alias.lower()
            # Check if alias is in column name
            if alias_lower in col_name_lower:
                # Prefer longer, more specific matches
                if len(alias_lower) > best_match_length:
                    best_match = col_type
                    best_match_length = len(alias_lower)

    # Return best match or default to string
    return best_match if best_match else "string"


def analyze_column_with_aliases(df: pd.DataFrame, column_name: str):
    """Column analyzer using aliases instead of LLM"""
    column_type = detect_column_type(column_name)
    
    result = {"column_name": column_name, "column_type": column_type}
    series = df[column_name]

    # Always counts
    result["count_null"] = int(series.isnull().sum())
    result["count_non_null"] = int(series.notnull().sum())

    # NUMERICAL
    if column_type == "numerical":
        num = pd.to_numeric(series, errors="coerce").dropna()
        if not num.empty:
            result["min_value"] = float(num.min())
            result["max_value"] = float(num.max())
            result["mean_value"] = float(num.mean())
        zero_count = int((pd.to_numeric(series, errors="coerce") == 0).sum())
        result["count_zero"] = zero_count

    # DATE
    elif column_type == "date":
        dates = pd.to_datetime(series, errors="coerce")
        valid_dates = dates.dropna()
        if not valid_dates.empty:
            result["oldest_date"] = str(valid_dates.min().date())
            result["newest_date"] = str(valid_dates.max().date())
            result["count_before_2000"] = int((valid_dates.dt.year < 2000).sum())
        invalid_dates = series.notnull() & dates.isnull()
        result["count_invalid_dates"] = int(invalid_dates.sum())

    # Country code
    elif column_type == "country_code":
        vals = [safe_str(v).strip() for v in series.dropna().tolist()]
        valid = sum(1 for v in vals if is_valid_country_code(v))
        invalid = len(vals) - valid
        result["valid_country_codes"] = valid
        result["invalid_country_codes"] = invalid
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}

    # Country name
    elif column_type == "country_name":
        vals = [safe_str(v).strip() for v in series.dropna().tolist()]
        valid = sum(1 for v in vals if is_valid_country_name(v))
        invalid = len(vals) - valid
        result["valid_countries"] = valid
        result["invalid_countries"] = invalid
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}

    elif column_type == "region_category":
        vals_idx = list(series.dropna().items())
        valid_count = 0
        invalid_count = 0
        assoc = find_assoc_country_col()

        for idx, val in vals_idx:
            region = safe_str(val).strip().upper()
            if not region:
                continue
            alpha2 = None
            if assoc and assoc in df.columns:
                cval = safe_str(df.at[idx, assoc]).strip()
                if detected_types.get(assoc) == "country_code":
                    alpha2 = cval.upper()
                else:
                    alpha2 = country_name_to_alpha2(cval)

            if alpha2:
                full_code = f"{alpha2}-{region}" if "-" not in region else region
                if is_valid_state_code(alpha2, full_code):
                    valid_count += 1
                else:
                    invalid_count += 1
            else:
                # No country found, can't validate
                invalid_count += 1

        result["valid_regions"] = valid_count
        result["invalid_regions"] = invalid_count
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}
    # Currency code
    elif column_type == "currency_code":
        vals = [safe_str(v).strip().upper() for v in series.dropna().tolist()]
        valid = sum(1 for v in vals if is_valid_currency(v))
        invalid = len(vals) - valid
        result["valid_currencies"] = valid
        result["invalid_currencies"] = invalid
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}

    # POSTAL CODE
    elif column_type == "postal_code":
        vals_idx = list(series.dropna().items())
        valid_count = 0
        invalid_count = 0
        assoc = find_assoc_country_col()
        for idx, val in vals_idx:
            postal = safe_str(val).strip()
            if not postal:
                continue
            alpha2 = None
            if assoc and assoc in df.columns:
                cval = safe_str(df.at[idx, assoc]).strip()
                if detected_types.get(assoc) == "country_code":
                    alpha2 = cval.upper()
                else:
                    alpha2 = country_name_to_alpha2(cval)
            if alpha2:
                if is_valid_postal(alpha2, postal):
                    valid_count += 1
                else:
                    invalid_count += 1
            else:
                if postal.replace("-", "").isdigit() and 3 <= len(postal.replace("-", "")) <= 10:
                    valid_count += 1
                else:
                    invalid_count += 1
        result["valid_postal_codes"] = valid_count
        result["invalid_postal_codes"] = invalid_count

    # ZIP CODE
    elif column_type == "zip_code":
        vals_idx = list(series.dropna().items())
        valid_count = 0
        invalid_count = 0
        mismatches = 0
        assoc = find_assoc_country_col()
        for idx, val in vals_idx:
            zipv = safe_str(val).strip()
            if not zipv:
                continue
            alpha2 = None
            if assoc and assoc in df.columns:
                cval = safe_str(df.at[idx, assoc]).strip()
                if detected_types.get(assoc) == "country_code":
                    alpha2 = cval.upper()
                else:
                    alpha2 = country_name_to_alpha2(cval)
            if alpha2:
                if alpha2 == "US":
                    if is_valid_zip(zipv):
                        valid_count += 1
                    else:
                        invalid_count += 1
                else:
                    mismatches += 1
            else:
                if is_valid_zip(zipv):
                    valid_count += 1
                else:
                    invalid_count += 1
        result["valid_zip_codes"] = valid_count
        result["invalid_zip_codes"] = invalid_count
        result["zip_country_mismatch"] = mismatches
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}

    # Phone
    elif column_type == "phone_number":
        vals = [safe_str(v).strip() for v in series.dropna().tolist()]
        valid = sum(1 for v in vals if is_valid_phone(v))
        invalid = len(vals) - valid
        result["valid_phones"] = valid
        result["invalid_phones"] = invalid

    # String / fallback
    else:
        blanks = sum(1 for v in series.dropna().astype(str).tolist() if str(v).strip() == "")
        result["blank_count"] = int(blanks)
        value_counts = series.value_counts().to_dict()
        result["value_counts"] = {str(k): int(v) for k, v in value_counts.items()}

    return result


# ----------------- FastAPI Routes -----------------

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Excel Analyzer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 10px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2 { color: #333; margin-bottom: 20px; }
            input[type="file"] { margin: 10px 0; }
            input[type="submit"] { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            input[type="submit"]:hover { background: #45a049; }
            .admin-btn { background: #2196F3; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 20px; }
            .admin-btn:hover { background: #0b7dda; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Upload Excel</h2>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input type="file" name="file" accept=".xlsx,.xls" required><br>
                <input type="submit" value="Upload">
            </form>
            <br>
            <a href="/admin_login" class="admin-btn">Admin Login</a>
        </div>
    </body>
    </html>
    """


@app.get("/admin_login", response_class=HTMLResponse)
def admin_login_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 10px; max-width: 400px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2 { color: #333; margin-bottom: 20px; }
            label { display: block; margin-top: 15px; font-weight: bold; color: #555; }
            input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            input[type="submit"] { background: #2196F3; color: white; padding: 12px; border: none; border-radius: 5px; cursor: pointer; width: 100%; margin-top: 20px; font-size: 16px; }
            input[type="submit"]:hover { background: #0b7dda; }
            .back-btn { text-align: center; margin-top: 15px; }
            .back-btn a { color: #2196F3; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Admin Login</h2>
            <form action="/admin_verify" method="post">
                <label>Username:</label>
                <input type="text" name="username" required>

                <label>Password:</label>
                <input type="password" name="password" required>

                <input type="submit" value="Login">
            </form>
            <div class="back-btn">
                <a href="/">← Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    """


@app.post("/admin_verify", response_class=HTMLResponse)
def admin_verify(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin_panel", status_code=303)
        response.set_cookie(key="admin_session", value="authenticated")
        return response
    else:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Failed</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; text-align: center; }
                .error { background: #f44336; color: white; padding: 20px; border-radius: 10px; max-width: 400px; margin: 50px auto; }
                a { color: white; text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Login Failed!</h2>
                <p>Invalid username or password.</p>
                <a href="/admin_login">Try Again</a>
            </div>
        </body>
        </html>
        """


@app.get("/admin_panel", response_class=HTMLResponse)
def admin_panel(admin_session: str = Cookie(None)):
    if admin_session != "authenticated":
        return RedirectResponse(url="/admin_login")

    aliases = load_aliases()

    rows = ""
    for col_type, alias_list in aliases.items():
        alias_str = ", ".join(alias_list)
        rows += f"""
        <tr>
            <td><strong>{col_type}</strong></td>
            <td><input type="text" name="{col_type}" value="{alias_str}" style="width: 100%; padding: 8px;"></td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 900px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h2 {{ color: #333; }}
            .instructions {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #2196F3; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            td {{ padding: 10px; border: 1px solid #ddd; }}
            td:first-child {{ background: #f5f5f5; width: 200px; }}
            input[type="submit"] {{ background: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 20px; }}
            input[type="submit"]:hover {{ background: #45a049; }}
            .logout {{ float: right; background: #f44336; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; }}
            .logout:hover {{ background: #da190b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Admin Panel - Manage Column Aliases
                <a href="/admin_logout" class="logout">Logout</a>
            </h2>

            <div class="instructions">
                <strong>Instructions:</strong><br>
                • Enter comma-separated aliases for each column type<br>
                • Example: <code>postal, postal_code, PSTLZ, POST_CODE1</code><br>
                • Column names containing any of these aliases will be automatically detected<br>
                • All aliases are case-insensitive
            </div>

            <form action="/admin_save" method="post">
                <table>
                    {rows}
                </table>
                <input type="submit" value="Save Aliases">
            </form>

            <br>
            <a href="/" style="color: #2196F3; text-decoration: none;">← Back to Home</a>
        </div>
    </body>
    </html>
    """


@app.post("/admin_save", response_class=HTMLResponse)
def admin_save(
        admin_session: str = Cookie(None),
        date: str = Form(""),
        phone_number: str = Form(""),
        country_name: str = Form(""),
        country_code: str = Form(""),
        region_category: str = Form(""),
        zip_code: str = Form(""),
        postal_code: str = Form(""),
        currency_code: str = Form(""),
        numerical: str = Form("")
):
    if admin_session != "authenticated":
        return RedirectResponse(url="/admin_login")

    new_aliases = {
        "date": [x.strip() for x in date.split(",") if x.strip()],
        "phone_number": [x.strip() for x in phone_number.split(",") if x.strip()],
        "country_name": [x.strip() for x in country_name.split(",") if x.strip()],
        "country_code": [x.strip() for x in country_code.split(",") if x.strip()],
        "region_category": [x.strip() for x in region_category.split(",") if x.strip()],  # ← ADD THIS
        "zip_code": [x.strip() for x in zip_code.split(",") if x.strip()],
        "postal_code": [x.strip() for x in postal_code.split(",") if x.strip()],
        "currency_code": [x.strip() for x in currency_code.split(",") if x.strip()],
        "numerical": [x.strip() for x in numerical.split(",") if x.strip()],
    }

    save_aliases(new_aliases)

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Saved</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; text-align: center; }
            .success { background: #4CAF50; color: white; padding: 20px; border-radius: 10px; max-width: 400px; margin: 50px auto; }
            a { color: white; text-decoration: underline; margin: 10px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="success">
            <h2>✓ Aliases Saved Successfully!</h2>
            <a href="/admin_panel">Back to Admin Panel</a>
            <a href="/">Go to Home</a>
        </div>
    </body>
    </html>
    """


@app.get("/admin_logout")
def admin_logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(key="admin_session")
    return response


@app.post("/upload", response_class=HTMLResponse)
async def upload(file: UploadFile):
    global uploaded_df, uploaded_filename, column_analysis, detected_types
    contents = await file.read()
    df = pd.read_excel(io.BytesIO(contents), dtype=object)
    uploaded_df = df
    uploaded_filename = file.filename

    column_analysis = {}
    detected_types = {}
    for col in df.columns:
        info = analyze_column_with_aliases(df, col)
        column_analysis[col] = info
        detected_types[col] = info.get("column_type", "string")

    return show_full_table()


@app.get("/show_full_table", response_class=HTMLResponse)
def show_full_table():
    if uploaded_df is None:
        return "<p>No file uploaded yet.</p><a href='/'>Upload</a>"

    df = uploaded_df
    type_html = "<ul>" + "".join([f"<li>{col}: {typ}</li>" for col, typ in detected_types.items()]) + "</ul>"
    table_html = generate_table_html(df)

    return f"""
    <h3>{uploaded_filename}</h3>
    <h4>Detected column types</h4>
    {type_html}
    <button onclick="window.location.href='/download_filtered'">Download Filtered</button><br><br>
    {table_html}

    <style>
    #overlay {{ position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.4); display:none; z-index:999; }}
    .popup {{ position: fixed; top:10%; left:25%; background:white; border:2px solid #333; border-radius:10px; padding:15px; z-index:1000; min-width:400px; max-height:80%; overflow-y:auto; }}
    .close-btn {{ float: right; cursor: pointer; color:red; font-size:18px; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ border:1px solid #ccc; padding:5px; }}
    th.col-header {{ background: #f2f2f2; cursor: pointer; }}
    .stats-table {{ border-collapse: collapse; margin: 10px 0; width: 100%; font-size: 12px; }}
    .stats-table th {{ background: #e0e0e0; padding: 4px; text-align: left; }}
    .stats-table td {{ padding: 4px; }}
    .stats-table button {{ font-size: 11px; padding: 2px 6px; }}
    </style>
    <div id="overlay"></div>
    <script>
    document.querySelectorAll('.col-header').forEach(header => {{
        header.addEventListener('click', () => {{
            const column = header.dataset.column;
            fetch(`/column_info?column=${{column}}`).then(r => r.text()).then(html => {{
                const overlay = document.getElementById('overlay');
                overlay.style.display = 'block';
                const popup = document.createElement('div');
                popup.classList.add('popup');
                popup.innerHTML = `<span class='close-btn'>&times;</span>` + html;
                document.body.appendChild(popup);
                popup.querySelector('.close-btn').onclick = () => {{ popup.remove(); overlay.style.display = 'none'; }};
                overlay.onclick = () => {{ popup.remove(); overlay.style.display = 'none'; }};
            }});
        }});
    }});
    </script>
    """


def generate_table_html(df: pd.DataFrame):
    headers = "".join([f"<th class='col-header' data-column='{col}'>{col}</th>" for col in df.columns])
    rows = ""
    for _, r in df.head(200).iterrows():
        rows += "<tr>" + "".join([f"<td>{safe_str(v)}</td>" for v in r.tolist()]) + "</tr>"
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"


@app.get("/column_info", response_class=HTMLResponse)
def column_info(column: str):
    if uploaded_df is None or column not in uploaded_df.columns:
        return "<p>No data</p>"

    info = column_analysis[column]
    col_type = info.get("column_type", "string")
    html = f"<b>{column}</b> ({col_type})<br><br>"
    html += f"Null rows: {info.get('count_null', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=null'\">Filter</button><br>"
    html += f"Non-null rows: {info.get('count_non_null', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=non_null'\">Filter</button><br>"

    if col_type == "numerical":
        html += f"Min value: {info.get('min_value', 'N/A')}<br>"
        html += f"Max value: {info.get('max_value', 'N/A')}<br>"
        html += f"Zero values: {info.get('count_zero', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=zero'\">Filter</button><br>"

    if col_type == "date":
        html += f"Oldest: {info.get('oldest_date', 'N/A')}<br>"
        html += f"Newest: {info.get('newest_date', 'N/A')}<br>"
        html += f"Year < 2000: {info.get('count_before_2000', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=before_2000'\">Filter</button><br>"
        html += f"Invalid dates: {info.get('count_invalid_dates', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_date'\">Filter</button><br>"

    if col_type == "string":
        html += f"Blank rows: {info.get('blank_count', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=blank'\">Filter</button><br>"

    if col_type == "currency_code":
        html += f"Valid currencies: {info.get('valid_currencies', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_currency'\">Filter</button><br>"
        html += f"Invalid currencies: {info.get('invalid_currencies', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_currency'\">Filter</button><br>"
        assoc = find_assoc_country_col()
        if assoc:
            mism = count_mismatch(assoc, column)
            html += f"Currency mismatch vs {assoc}: {mism} <button onclick=\"window.location.href='/filter?column={column}&mode=currency_mismatch&country_col={assoc}'\">Filter</button><br>"

    if col_type == "phone_number":
        html += f"Valid phones: {info.get('valid_phones', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_phone'\">Filter</button><br>"
        html += f"Invalid phones: {info.get('invalid_phones', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_phone'\">Filter</button><br>"

    if col_type == "country_code":
        html += f"Valid country codes: {info.get('valid_country_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_ccode'\">Filter</button><br>"
        html += f"Invalid country codes: {info.get('invalid_country_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_ccode'\">Filter</button><br>"

    if col_type == "country_name":
        html += f"Valid countries: {info.get('valid_countries', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_country'\">Filter</button><br>"
        html += f"Invalid countries: {info.get('invalid_countries', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_country'\">Filter</button><br>"

    if col_type == "region_category":
        html += f"Valid regions: {info.get('valid_regions', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_region'\">Filter</button><br>"
        html += f"Invalid regions: {info.get('invalid_regions', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_region'\">Filter</button><br>"

    if col_type == "postal_code":
        html += f"Valid postal codes: {info.get('valid_postal_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_postal'\">Filter</button><br>"
        html += f"Invalid postal codes: {info.get('invalid_postal_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_postal'\">Filter</button><br>"

    if col_type == "zip_code":
        html += f"Valid zip codes: {info.get('valid_zip_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=valid_zip'\">Filter</button><br>"
        html += f"Invalid zip codes: {info.get('invalid_zip_codes', 0)} <button onclick=\"window.location.href='/filter?column={column}&mode=invalid_zip'\">Filter</button><br>"
        assoc = find_assoc_country_col()
        if assoc:
            mism = info.get("zip_country_mismatch", 0)
            html += f"ZIP mismatch vs {assoc}: {mism} <button onclick=\"window.location.href='/filter?column={column}&mode=zip_mismatch&country_col={assoc}'\">Filter</button><br>"

    # VALUE COUNTS TABLE
    if "value_counts" in info and info["value_counts"]:
        html += "<br><b>Value Statistics:</b><br>"
        html += "<table class='stats-table'>"
        html += "<thead><tr><th>Value</th><th>Count</th><th>Action</th></tr></thead>"
        html += "<tbody>"
        for value, count in sorted(info["value_counts"].items(), key=lambda x: x[1], reverse=True):
            html += f"<tr><td>{value}</td><td>{count}</td><td><button onclick=\"window.location.href='/filter?column={column}&mode=value_equals&value={value}'\">Filter</button></td></tr>"
        html += "</tbody></table>"

    return html


@app.get("/filter", response_class=HTMLResponse)
def filter_rows(column: str, mode: str, country_col: Union[str, None] = None, value: Union[str, None] = None):
    global last_filtered_df
    if uploaded_df is None:
        return "<p>No data</p>"
    df = uploaded_df
    mode = mode.lower()
    filtered = df

    if mode == "null":
        filtered = df[df[column].isnull()]
    elif mode == "non_null":
        filtered = df[df[column].notnull()]
    elif mode == "blank":
        filtered = df[df[column].astype(str).str.strip() == ""]
    elif mode == "zero":
        num_series = pd.to_numeric(df[column], errors="coerce")
        filtered = df[num_series == 0]
    elif mode == "before_2000":
        series = pd.to_datetime(df[column], errors="coerce")
        filtered = df[series.dt.year < 2000]
    elif mode == "invalid_date":
        series = pd.to_datetime(df[column], errors="coerce")
        invalid_mask = df[column].notnull() & series.isnull()
        filtered = df[invalid_mask]
    elif mode == "valid_phone":
        filtered = df[df[column].apply(lambda x: is_valid_phone(safe_str(x)))]
    elif mode == "invalid_phone":
        filtered = df[~df[column].apply(lambda x: is_valid_phone(safe_str(x)))]
    elif mode == "valid_currency":
        filtered = df[df[column].apply(lambda x: is_valid_currency(safe_str(x).upper()))]
    elif mode == "invalid_currency":
        filtered = df[~df[column].apply(lambda x: is_valid_currency(safe_str(x).upper()))]
    elif mode == "currency_mismatch":
        assoc = country_col or find_assoc_country_col()
        rows = []
        for idx, row in df[[assoc, column]].dropna().iterrows():
            cval = safe_str(row[assoc]).strip()
            cur = safe_str(row[column]).strip().upper()
            if not cval or not cur:
                continue
            if detected_types.get(assoc) == "country_code":
                alpha2 = cval.upper()
            else:
                alpha2 = country_name_to_alpha2(cval)
            if not alpha2:
                continue
            if cur[:2] != alpha2:
                rows.append(idx)
        filtered = df.loc[rows]
    elif mode == "valid_country":
        filtered = df[df[column].apply(lambda x: is_valid_country_name(safe_str(x)))]
    elif mode == "invalid_country":
        filtered = df[~df[column].apply(lambda x: is_valid_country_name(safe_str(x)))]
    elif mode == "valid_region":
        assoc = country_col or find_assoc_country_col()
        rows = []
        if assoc and assoc in df.columns:
            for idx, row in df[[assoc, column]].dropna().iterrows():
                cval = safe_str(row[assoc]).strip()
                region = safe_str(row[column]).strip()
                if not cval or not region:
                    continue
                alpha2 = cval.upper() if detected_types.get(assoc) == "country_code" else country_name_to_alpha2(cval)
                if alpha2:
                    full_code = f"{alpha2}-{region}" if "-" not in region else region
                    if is_valid_state_code(alpha2, full_code):
                        rows.append(idx)
        filtered = df.loc[rows] if rows else df.iloc[0:0]

    elif mode == "invalid_region":
        assoc = country_col or find_assoc_country_col()
        rows = []
        if assoc and assoc in df.columns:
            for idx, row in df[[assoc, column]].dropna().iterrows():
                cval = safe_str(row[assoc]).strip()
                region = safe_str(row[column]).strip()
                if not cval or not region:
                    continue
                alpha2 = cval.upper() if detected_types.get(assoc) == "country_code" else country_name_to_alpha2(cval)
                if alpha2:
                    full_code = f"{alpha2}-{region}" if "-" not in region else region
                    if not is_valid_state_code(alpha2, full_code):
                        rows.append(idx)
                else:
                    rows.append(idx)
        filtered = df.loc[rows] if rows else df.iloc[0:0]
    elif mode == "valid_ccode":
        filtered = df[df[column].apply(lambda x: is_valid_country_code(safe_str(x)))]
    elif mode == "invalid_ccode":
        filtered = df[~df[column].apply(lambda x: is_valid_country_code(safe_str(x)))]
    elif mode == "value_equals":
        if value is not None:
            filtered = df[df[column].astype(str) == value]
    elif mode == "valid_postal":
        assoc = country_col or find_assoc_country_col()
        rows = []
        for idx, row in df[[assoc, column]].dropna().iterrows() if assoc and assoc in df.columns else df[
            [column]].dropna().iterrows():
            if assoc and assoc in df.columns:
                cval = safe_str(row[assoc]).strip()
                postal = safe_str(row[column]).strip()
                if not cval or not postal:
                    continue
                if detected_types.get(assoc) == "country_code":
                    alpha2 = cval.upper()
                else:
                    alpha2 = country_name_to_alpha2(cval)
                if alpha2 and is_valid_postal(alpha2, postal):
                    rows.append(idx)
                elif not alpha2 and postal.replace("-", "").isdigit() and 3 <= len(postal.replace("-", "")) <= 10:
                    rows.append(idx)
            else:
                postal = safe_str(row[column]).strip()
                if postal.replace("-", "").isdigit() and 3 <= len(postal.replace("-", "")) <= 10:
                    rows.append(idx)
        filtered = df.loc[rows]
    elif mode == "invalid_postal":
        assoc = country_col or find_assoc_country_col()
        rows = []
        for idx, row in df[[assoc, column]].dropna().iterrows() if assoc and assoc in df.columns else df[
            [column]].dropna().iterrows():
            if assoc and assoc in df.columns:
                cval = safe_str(row[assoc]).strip()
                postal = safe_str(row[column]).strip()
                if not cval or not postal:
                    continue
                if detected_types.get(assoc) == "country_code":
                    alpha2 = cval.upper()
                else:
                    alpha2 = country_name_to_alpha2(cval)
                if alpha2 and not is_valid_postal(alpha2, postal):
                    rows.append(idx)
                elif not alpha2 and not (postal.replace("-", "").isdigit() and 3 <= len(postal.replace("-", "")) <= 10):
                    rows.append(idx)
            else:
                postal = safe_str(row[column]).strip()
                if not (postal.replace("-", "").isdigit() and 3 <= len(postal.replace("-", "")) <= 10):
                    rows.append(idx)
        filtered = df.loc[rows]
    elif mode == "valid_zip":
        assoc = country_col or find_assoc_country_col()
        rows = []
        if assoc and assoc in df.columns:
            for idx, row in df[[assoc, column]].dropna().iterrows():
                cval = safe_str(row[assoc]).strip()
                zipv = safe_str(row[column]).strip()
                if not cval or not zipv:
                    continue
                alpha2 = cval.upper() if detected_types.get(assoc) == "country_code" else country_name_to_alpha2(cval)
                if alpha2 == "US" and is_valid_zip(zipv):
                    rows.append(idx)
        else:
            for idx, row in df[[column]].dropna().iterrows():
                zipv = safe_str(row[column]).strip()
                if is_valid_zip(zipv):
                    rows.append(idx)
        filtered = df.loc[rows]
    elif mode == "invalid_zip":
        assoc = country_col or find_assoc_country_col()
        rows = []
        if assoc and assoc in df.columns:
            for idx, row in df[[assoc, column]].dropna().iterrows():
                cval = safe_str(row[assoc]).strip()
                zipv = safe_str(row[column]).strip()
                if not cval or not zipv:
                    continue
                alpha2 = cval.upper() if detected_types.get(assoc) == "country_code" else country_name_to_alpha2(cval)
                if alpha2 == "US" and not is_valid_zip(zipv):
                    rows.append(idx)
        else:
            for idx, row in df[[column]].dropna().iterrows():
                zipv = safe_str(row[column]).strip()
                if not is_valid_zip(zipv):
                    rows.append(idx)
        filtered = df.loc[rows]
    elif mode == "zip_mismatch":
        assoc = country_col or find_assoc_country_col()
        rows = []
        if assoc and assoc in df.columns:
            for idx, row in df[[assoc, column]].dropna().iterrows():
                cval = safe_str(row[assoc]).strip()
                zipv = safe_str(row[column]).strip()
                if not cval or not zipv:
                    continue
                alpha2 = cval.upper() if detected_types.get(assoc) == "country_code" else country_name_to_alpha2(cval)
                if alpha2 and alpha2 != "US":
                    rows.append(idx)
                elif alpha2 == "US" and not is_valid_zip(zipv):
                    rows.append(idx)
        filtered = df.loc[rows]

    last_filtered_df = filtered
    html = generate_table_html(filtered)
    filter_desc = f"{mode}" if value is None else f"{mode} = {value}"
    return f"""
    <h3>Filtered — {column} ({filter_desc})</h3>
    <p>Showing {len(filtered)} rows</p>
    <button onclick="window.location.href='/show_full_table'">Back Full</button>
    <button onclick="window.location.href='/download_filtered'">Download</button><br><br>

    <style>
    table {{ border-collapse: collapse; width:100%; margin-top: 20px; }}
    th, td {{ border:1px solid #ccc; padding:8px; text-align: left; }}
    th {{ background: #f2f2f2; font-weight: bold; }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
    tr:hover {{ background-color: #f5f5f5; }}
    </style>

    {html}
    """


@app.get("/download_filtered")
def download_filtered():
    global last_filtered_df
    if last_filtered_df is None or last_filtered_df.empty:
        return HTMLResponse("<p>No data to download</p>")
    buf = io.BytesIO()
    last_filtered_df.to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=filtered.xlsx"})


def find_assoc_country_col():
    for c, t in detected_types.items():
        if t == "country_code":
            return c
    for c, t in detected_types.items():
        if t == "country_name":
            return c
    return None


def country_name_to_alpha2(name: str):
    try:
        c = pycountry.countries.get(name=name)
        if c:
            return c.alpha_2
        for cc in pycountry.countries:
            if name.lower() == cc.name.lower():
                return cc.alpha_2
            if hasattr(cc, 'official_name') and name.lower() == cc.official_name.lower():
                return cc.alpha_2
    except:
        return None
    return None


def count_mismatch(country_col: str, currency_col: str):
    if uploaded_df is None: return 0
    df = uploaded_df
    mismatches = 0
    for idx, row in df[[country_col, currency_col]].dropna().iterrows():
        cval = safe_str(row[country_col]).strip()
        cur = safe_str(row[currency_col]).strip().upper()
        if not cval or not cur:
            continue
        if detected_types.get(country_col) == "country_code":
            alpha2 = cval.upper()
        else:
            alpha2 = country_name_to_alpha2(cval)
        if not alpha2:
            continue
        if cur[:2] != alpha2:
            mismatches += 1
    return mismatches

# ---------------------------------------------------------
# Run the app with:
# uvicorn final2:app --reload
# ---------------------------------------------------------