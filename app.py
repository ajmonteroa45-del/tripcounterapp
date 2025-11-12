# app.py - Trip Counter (Flask)
print("DEBUG: app.py ha iniciado correctamente")

import os
import json
import logging
import sys
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from requests_oauthlib import OAuth2Session
from google.oauth2 import service_account
import gspread
import base64
from google.oauth2.service_account import Credentials

# ----------------------------
# CONFIG / LOGGING
# ----------------------------
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, static_folder="static", template_folder="templates")
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)

# Environment variables (must be configured)
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "tripcounter-service-account.json")

if not FLASK_SECRET_KEY:
    app.logger.warning("⚠️ FLASK_SECRET_KEY not set - using temporary key.")
    app.secret_key = os.urandom(24)
else:
    app.secret_key = FLASK_SECRET_KEY

# OAuth endpoints and scopes
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]
GSHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

# Fixed airport fee
AIRPORT_FEE = 6.50

# --- CONSTANTES DE HOJAS DE CÁLCULO ---
# Viajes
TRIPS_WS_NAME = "TripCounter_Trips"
TRIPS_HEADERS = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Propina","Aeropuerto","Total"]
# Bonos
BONUS_WS_NAME = "TripCounter_Bonuses"
BONUS_HEADERS = ["Fecha", "Bono total"]
BONUS_RULES = {
    'LUN_JUE': {13: 16, 17: 9, 21: 12, 25: 16},
    'VIE_SAB': {13: 15, 17: 10, 21: 13, 25: 15},
    'DOM': {12: 14, 16: 10, 19: 11, 23: 14},
}
# Gastos
GASTOS_WS_NAME = "TripCounter_Gastos"
GASTOS_HEADERS = ["Fecha", "Hora", "Monto", "Categoría", "Descripción"]
# Presupuesto
PRESUPUESTO_WS_NAME = "TripCounter_Presupuesto"
PRESUPUESTO_HEADERS = ["alias", "categoria", "monto", "fecha_pago", "pagado"] 
# Extras
EXTRAS_WS_NAME = "TripCounter_Extras"
EXTRAS_HEADERS = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Total"]


# ----------------------------
# Debug inicial visible en Render logs
# ----------------------------
@app.before_request
def startup_debug():
    """Imprime variables de entorno clave solo una vez."""
    if not getattr(app, "_startup_debug_done", False):
        print("⚙️ DEBUG desde Flask startup:")
        for key in ["SERVICE_ACCOUNT_B64", "FLASK_SECRET_KEY", "OAUTH_CLIENT_ID"]:
            print(f"{key}: {'✅ OK' if os.getenv(key) else '❌ MISSING'}")
        app._startup_debug_done = True

# ----------------------------
# Google Sheets Client & Utilitarios
# ----------------------------
def get_gspread_client():
    # ... (Tu código para obtener el cliente de GSpread) ...
    b64_credentials = os.getenv("SERVICE_ACCOUNT_B64")
    print("DEBUG: SERVICE_ACCOUNT_B64 presente:", bool(b64_credentials))

    if not b64_credentials:
        raise FileNotFoundError("Variable SERVICE_ACCOUNT_B64 no encontrada en Render")

    credentials_json = base64.b64decode(b64_credentials).decode("utf-8")
    creds_dict = json.loads(credentials_json)

    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
    )

    client = gspread.authorize(credentials)
    return client

# app.py (Reemplaza la función ensure_sheet_with_headers con esta versión)

def ensure_sheet_with_headers(client, ws_name, headers):
    """
    Abre el Workbook (archivo) con el nombre 'ws_name' (ej: 'TripCounter_Trips')
    y asegura que la primera fila contenga las cabeceras correctas.
    """
    WORKBOOK_NAME = ws_name # El nombre del archivo es ahora el nombre de la hoja (pestaña)

    # 1. Abrir el Workbook (Archivo principal de Google Sheets)
    try:
        # Abre el archivo por su nombre completo (ej: 'TripCounter_Trips')
        workbook = client.open(WORKBOOK_NAME) 
    except gspread.WorksheetNotFound:
        # Este error ocurre si el archivo con ese nombre no existe o la cuenta de servicio no tiene acceso
        app.logger.error(f"❌ ERROR: El archivo principal '{WORKBOOK_NAME}' no fue encontrado. Verifica el acceso de la Cuenta de Servicio.")
        raise Exception(f"Error de configuración: Archivo '{WORKBOOK_NAME}' no encontrado o sin permisos.")
        
    # 2. Obtener la Pestaña (Worksheet)
    # Asumimos que la hoja de trabajo principal es la primera (index 0)
    # Si tienes varias pestañas dentro del archivo, tendrías que cambiar esto.
    ws = workbook.get_worksheet(0)
        
    # 3. Asegurar que las Cabeceras son correctas
    try:
        current_headers = ws.row_values(1)
        if current_headers != headers:
            app.logger.warning(f"⚠️ Las cabeceras de '{WORKBOOK_NAME}' no coinciden. Sobrescribiendo.")
            # Borrar la primera fila y reinsertar las correctas
            ws.delete_rows(1)
            ws.insert_row(headers, 1)
    except Exception as e:
        app.logger.error(f"Error al verificar cabeceras en {WORKBOOK_NAME}: {e}")
        # Intentar insertar si hay problemas, asumiendo que estaba vacío
        try:
            ws.insert_row(headers, 1)
        except:
            pass 

    return ws



# ----------------------------
# FUNCIONES DE LÓGICA DE NEGOCIO (Bonos)
# ----------------------------
def get_bonus_type(day_of_week):
    """Retorna la clave del tipo de bono basado en el día (0=Lunes, 6=Domingo)"""
    if 0 <= day_of_week <= 3: 
        return 'LUN_JUE'
    elif day_of_week in (4, 5): 
        return 'VIE_SAB'
    elif day_of_week == 6: 
        return 'DOM'
    return None

def calculate_current_bonus(records_today):
    """Calcula el bono total aplicable para el día basado en el número de viajes."""
    if not records_today:
        return 0.0

    try:
        trip_date = datetime.strptime(records_today[0]["Fecha"], '%Y-%m-%d').date()
    except Exception:
        return 0.0
        
    day_of_week = trip_date.weekday()
    num_trips = len(records_today)
    
    rules = BONUS_RULES.get(get_bonus_type(day_of_week), {})
    total_bonus = 0.0
    
    sorted_goals = sorted(rules.keys())
    
    for goal in sorted_goals:
        if num_trips >= goal:
            total_bonus += rules[goal]

    return total_bonus

def update_daily_bonus_sheet(client, fecha, total_bonus):
    """Guarda o actualiza el bono diario total en la hoja 'TripCounter_Bonuses'."""
    ws_bonuses = ensure_sheet_with_headers(client, BONUS_WS_NAME, BONUS_HEADERS)
    
    records = ws_bonuses.get_all_records()
    found = False
    
    for i, r in enumerate(records):
        if str(r.get("Fecha")) == str(fecha):
            row_index = i + 2 
            col_index = BONUS_HEADERS.index("Bono total") + 1
            ws_bonuses.update_cell(row_index, col_index, total_bonus)
            found = True
            break
            
    if not found:
        new_row = [fecha, total_bonus]
        ws_bonuses.append_row(new_row)
        
    return total_bonus


# ----------------------------
# ROUTES: Auth
# ----------------------------
@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        app.logger.error("❌ OAUTH env vars not configured (OAUTH_CLIENT_ID/OAUTH_CLIENT_SECRET/OAUTH_REDIRECT_URI).")
        return "<h3>OAuth configuration missing. Contact admin.</h3>", 500

    oauth = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    authorization_url, state = oauth.authorization_url(
        AUTHORIZE_URL, access_type="offline", prompt="select_account"
    )
    session['oauth_state'] = state
    app.logger.info("Redirecting to Google OAuth...")
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    try:
        oauth = OAuth2Session(CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
        token = oauth.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.url)
        # decode email from token using jwt library is optional; we can request userinfo
        userinfo = oauth.get("https://www.googleapis.com/oauth2/v2/userinfo").json()
        session['email'] = userinfo.get('email')
        app.logger.info(f"User logged in: {session.get('email')}")
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"OAuth callback error: {e}")
        return f"<h3>Authentication failed: {e}</h3>", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ----------------------------
# ROUTES: UI
# ----------------------------
@app.route("/")
def index():
    email = session.get('email')
    # If not logged in, show login button
    if not email:
        return render_template("login.html")
    # Show home panel & reminders
    try:
        client = get_gspread_client()
        # load presupuestos to show reminders (if sheet exists)
        try:
            ws_pres = ensure_sheet_with_headers(client, PRESUPUESTO_WS_NAME, PRESUPUESTO_HEADERS)
            records = ws_pres.get_all_records()
            
            reminders = []
            today = date.today()
            for r in records:
                try:
                    fp = datetime.strptime(r.get("fecha_pago"), "%Y-%m-%d").date()
                except Exception:
                    continue
                days_left = (fp - today).days
                if r.get("pagado") in ("True","true","TRUE"):
                    continue
                # Recordatorios de 3 días y fecha de pago
                if days_left == 3:
                    reminders.append({"type":"3days","categoria":r.get("categoria"),"monto":r.get("monto")})
                elif days_left == 0:
                    reminders.append({"type":"due","categoria":r.get("categoria"),"monto":r.get("monto")})
        except Exception as e:
            app.logger.error(f"Error cargando recordatorios: {e}")
            reminders = []
    except Exception as e:
        app.logger.error(f"Error conectando a GSheets: {e}")
        reminders = []

    return render_template("home.html", email=email, reminders=reminders)

@app.route("/viajes")
def viajes_page():
    if not session.get('email'):
        return redirect(url_for("login"))
    return render_template("viajes.html", email=session.get('email'))

@app.route("/extras")
def extras_page():
    if not session.get('email'):
        return redirect(url_for("login"))
    return render_template("extras.html", email=session.get('email'))

@app.route("/presupuesto")
def presupuesto_page():
    if not session.get('email'):
        return redirect(url_for("login"))
    return render_template("presupuesto.html", email=session.get('email'))

# ----------------------------
# API: Trips (Ruta Unificada)
# ----------------------------
@app.route("/api/trips", methods=["GET", "POST"])
def api_trips():
    """
    GET: optional ?date=YYYY-MM-DD returns trips and bonus for that date (defaults to today)
    POST: Registers a trip, recalculates, and updates the daily bonus.
    """
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    client = get_gspread_client()
    ws_trips = ensure_sheet_with_headers(client, TRIPS_WS_NAME, TRIPS_HEADERS)
    ws_bonuses = ensure_sheet_with_headers(client, BONUS_WS_NAME, BONUS_HEADERS)

    if request.method == "GET":
        qdate = request.args.get("date") or date.today().isoformat()
        
        all_trips = ws_trips.get_all_records()
        filtered_trips = [r for r in all_trips if str(r.get("Fecha")) == str(qdate)]
        
        all_bonuses = ws_bonuses.get_all_records()
        current_bonus = next((float(r.get('Bono total', 0.0)) for r in all_bonuses if str(r.get("Fecha")) == str(qdate)), 0.0)
        
        return jsonify({"trips": filtered_trips, "bonus": current_bonus})

    # POST (Registro de Viaje)
    body = request.get_json() or {}
    fecha = body.get("fecha") or date.today().isoformat()
    hora_inicio = str(body.get("hora_inicio","")).strip()
    hora_fin = str(body.get("hora_fin","")).strip()
    
    try:
        monto = float(body.get("monto", 0))
    except Exception:
        return jsonify({"error":"invalid_monto"}), 400
        
    propina = 0.0
    try:
        propina = float(body.get("propina", 0)) if body.get("propina") else 0.0
    except Exception:
        propina = 0.0
            
    aeropuerto_flag = bool(body.get("aeropuerto", False))
    aeropuerto_val = AIRPORT_FEE if aeropuerto_flag else 0.0 
    total = round(monto + propina + aeropuerto_val, 2)

    all_trips = ws_trips.get_all_records()

    for r in all_trips:
        if str(r.get("Fecha")) == str(fecha) and str(r.get("Hora inicio")) == hora_inicio and str(r.get("Hora fin")) == hora_fin:
            return jsonify({"error":"duplicate"}), 409

    same_date_count = sum(1 for r in all_trips if str(r.get("Fecha")) == str(fecha))
    numero = same_date_count + 1

    row = [fecha, numero, hora_inicio, hora_fin, monto, propina, aeropuerto_val, total]
    ws_trips.append_row(row)
    app.logger.info(f"New trip appended: {row}")
    
    all_trips_after_post = ws_trips.get_all_records()
    trips_today = [r for r in all_trips_after_post if str(r.get("Fecha")) == str(fecha)]
    
    current_bonus = calculate_current_bonus(trips_today)
    update_daily_bonus_sheet(client, fecha, current_bonus)
    
    return jsonify({"status":"ok","trip":dict(zip(TRIPS_HEADERS,row)), "new_bonus": current_bonus}), 201

# ----------------------------
# API: Expenses (Gastos)
# ----------------------------
@app.route("/api/expenses", methods=["GET", "POST"])
def api_expenses():
    """
    GET: optional ?date=YYYY-MM-DD returns expenses for that date (defaults to today)
    POST: JSON with keys: fecha (optional), hora (optional), monto, categoria, descripcion
    """
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    client = get_gspread_client()
    ws_gastos = ensure_sheet_with_headers(client, GASTOS_WS_NAME, GASTOS_HEADERS)

    if request.method == "GET":
        qdate = request.args.get("date") or date.today().isoformat()
        
        all_expenses = ws_gastos.get_all_records()
        filtered_expenses = [r for r in all_expenses if str(r.get("Fecha")) == str(qdate)]
        
        return jsonify(filtered_expenses)
    
    body = request.get_json() or {}
    
    fecha = body.get("fecha") or date.today().isoformat()
    hora = body.get("hora") or datetime.now().strftime('%H:%M')
    categoria = str(body.get("categoria", "")).strip()
    descripcion = str(body.get("descripcion", "")).strip()
    
    try:
        monto = float(body.get("monto", 0))
        if monto <= 0:
            return jsonify({"error": "monto_invalido", "message": "El monto debe ser un valor positivo."}), 400
    except Exception:
        return jsonify({"error": "monto_invalido", "message": "El monto debe ser numérico."}), 400

    row = [fecha, hora, monto, categoria, descripcion]
    ws_gastos.append_row(row)
    app.logger.info(f"New expense appended: {row}")
    
    return jsonify({"status":"ok", "expense": dict(zip(GASTOS_HEADERS, row))}), 201


# ----------------------------
# API: Extras
# ----------------------------
@app.route("/api/extras", methods=["GET","POST"])
def api_extras():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    client = get_gspread_client()
    ws = ensure_sheet_with_headers(client, EXTRAS_WS_NAME, EXTRAS_HEADERS)
    if request.method == "GET":
        qdate = request.args.get("date") or date.today().isoformat()
        records = ws.get_all_records()
        filtered = [r for r in records if str(r.get("Fecha")) == str(qdate)]
        return jsonify(filtered)

    body = request.get_json() or {}
    fecha = body.get("fecha") or date.today().isoformat()
    hi = str(body.get("hora_inicio","")).strip()
    hf = str(body.get("hora_fin","")).strip()
    try:
        monto = float(body.get("monto",0))
    except Exception:
        monto = 0.0

    records = ws.get_all_records()
    for r in records:
        if str(r.get("Fecha")) == str(fecha) and str(r.get("Hora inicio")) == hi and str(r.get("Hora fin")) == hf:
            return jsonify({"error":"duplicate"}), 409

    same_date_count = sum(1 for r in records if str(r.get("Fecha")) == str(fecha))
    numero = same_date_count + 1
    total = round(monto,2)
    row = [fecha, numero, hi, hf, monto, total]
    ws.append_row(row)
    app.logger.info(f"New extra appended: {row}")
    return jsonify({"status":"ok","extra":dict(zip(EXTRAS_HEADERS,row))}), 201

# ----------------------------
# API: Presupuesto
# ----------------------------
@app.route("/api/presupuesto", methods=["GET","POST","PUT"])
def api_presupuesto():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    client = get_gspread_client()
    # Usamos las constantes globales aquí
    ws = ensure_sheet_with_headers(client, PRESUPUESTO_WS_NAME, PRESUPUESTO_HEADERS)

    if request.method == "GET":
        records = ws.get_all_records()
        return jsonify(records)

    if request.method == "POST":
        body = request.get_json() or {}
        alias = session.get('email')
        categoria = body.get("categoria","").strip()
        monto = body.get("monto",0)
        fecha_pago = body.get("fecha_pago")
        if not categoria or not fecha_pago:
            return jsonify({"error":"missing_fields"}), 400
        
        # Validación de Monto
        try:
            monto = float(monto)
            if monto <= 0:
                 return jsonify({"error": "monto_invalido", "message": "El monto debe ser un valor positivo."}), 400
        except Exception:
            return jsonify({"error": "monto_invalido", "message": "El monto debe ser numérico."}), 400

        row = [alias, categoria, monto, fecha_pago, "False"]
        ws.append_row(row)
        return jsonify({"status":"ok","entry":dict(zip(PRESUPUESTO_HEADERS,row))}), 201

    # PUT -> mark as paid; expects 'row_index' (1-based)
    if request.method == "PUT":
        body = request.get_json() or {}
        row_index = body.get("row_index")
        if not row_index:
            return jsonify({"error":"missing_row_index"}), 400
        try:
            # set pagado column (5th, index 5) to True for given row
            ws.update_cell(int(row_index), PRESUPUESTO_HEADERS.index("pagado") + 1, "True")
            return jsonify({"status":"ok"}), 200
        except Exception as e:
            app.logger.error(f"Error actualizando celda en GSheets: {e}")
            return jsonify({"error":f"Error al actualizar la hoja: {e}"}), 500

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    print("DEBUG: Flask app ejecutándose directamente")
    # Para ejecutar localmente, descomentar la siguiente línea
    # app.run(host="0.0.0.0", port=10000, debug=True)
