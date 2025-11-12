 # app.py - Trip Counter (Flask)
print("DEBUG: app.py ha iniciado correctamente")

import os
import json
import logging
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from requests_oauthlib import OAuth2Session
from google.oauth2 import service_account
import gspread
import base64
from google.oauth2.service_account import Credentials

# --- CONSTANTES ---
GASTOS_WS_NAME = "TripCounter_Gastos"
GASTOS_HEADERS = ["Fecha", "Hora", "Monto", "Categoría", "Descripción"]
# --- FIN CONSTANTES ---

# --- CONSTANTES DE PRESUPUESTO (Añadir a app.py) ---
PRESUPUESTO_WS_NAME = "TripCounter_Presupuesto"
PRESUPUESTO_HEADERS = ["alias", "categoria", "monto", "fecha_pago", "pagado"] 
# --- FIN CONSTANTES DE PRESUPUESTO ---


# ----------------------------
# CONFIG / LOGGING
# ----------------------------
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, static_folder="static", template_folder="templates")
import sys
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.DEBUG)
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

# OAuth endpoints
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# Google Sheets scopes
GSHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

# Fixed airport fee
AIRPORT_FEE = 6.50

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
# Google Sheets Client
# ----------------------------
def get_gspread_client():
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
            "https://www.googleapis.com/auth/drive.file"8
        ]
    )

    client = gspread.authorize(credentials)
    return client

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
        id_token = token.get('id_token')
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
            ws_pres = ensure_sheet_with_headers(client, "TripCounter_Presupuesto", ["alias","categoria","monto","fecha_pago","pagado"])
            records = ws_pres.get_all_records()
            # compute simple reminders for this email
            reminders = []
            today = date.today()
            for r in records:
                # filter by email if alias stored; if not, assume all
                try:
                    fp = datetime.strptime(r.get("fecha_pago"), "%Y-%m-%d").date()
                except Exception:
                    continue
                days_left = (fp - today).days
                if r.get("pagado") in ("True","true","TRUE"):
                    continue
                if days_left == 3:
                    reminders.append({"type":"3days","categoria":r.get("categoria"),"monto":r.get("monto")})
                elif days_left == 0:
                    reminders.append({"type":"due","categoria":r.get("categoria"),"monto":r.get("monto")})
        except Exception:
            reminders = []
    except Exception:
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

from datetime import datetime, date
from flask import jsonify, request, session
# Asegúrate de importar tus funciones de GSheets:
# from tu_modulo import get_gspread_client, ensure_sheet_with_headers

# --- CONSTANTES DE BONIFICACIÓN ---
# Bonos en Soles (S/)
BONUS_RULES = {
    # Lunes (0) a Jueves (3)
    'LUN_JUE': {13: 16, 17: 9, 21: 12, 25: 16},
    # Viernes (4) y Sábado (5)
    'VIE_SAB': {13: 15, 17: 10, 21: 13, 25: 15},
    # Domingo (6)
    'DOM': {12: 14, 16: 10, 19: 11, 23: 14},
}

TRIPS_WS_NAME = "TripCounter_Trips"
TRIPS_HEADERS = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Propina","Aeropuerto","Total"]
BONUS_WS_NAME = "TripCounter_Bonuses"
BONUS_HEADERS = ["Fecha", "Bono total"]

# --- FUNCIONES DE LÓGICA DE NEGOCIO ---

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
    
    # Sumar los bonos acumulativos al alcanzar las metas
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
    
    # Buscar si ya existe un registro para esa fecha para actualizarlo
    for i, r in enumerate(records):
        if str(r.get("Fecha")) == str(fecha):
            # i+2: fila real; +1: columna de "Bono total"
            row_index = i + 2 
            col_index = BONUS_HEADERS.index("Bono total") + 1
            ws_bonuses.update_cell(row_index, col_index, total_bonus)
            found = True
            break
            
    if not found:
        # Añadir nueva fila si la fecha no existe
        new_row = [fecha, total_bonus]
        ws_bonuses.append_row(new_row)
        
    return total_bonus

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
    ws_bonuses = ensure_sheet_with_headers(client, BONUS_WS_NAME, BONUS_HEADERS) # Solo para asegurar la creación si no existe

    if request.method == "GET":
        qdate = request.args.get("date") or date.today().isoformat()
        
        # 1. Obtener viajes del día
        all_trips = ws_trips.get_all_records()
        filtered_trips = [r for r in all_trips if str(r.get("Fecha")) == str(qdate)]
        
        # 2. Obtener bono del día
        all_bonuses = ws_bonuses.get_all_records()
        # next() busca el bono para la fecha, sino usa 0.0 por defecto
        current_bonus = next((float(r.get('Bono total', 0.0)) for r in all_bonuses if str(r.get("Fecha")) == str(qdate)), 0.0)
        
        return jsonify({"trips": filtered_trips, "bonus": current_bonus})

    # POST (Registro de Viaje)
    body = request.get_json() or {}
    fecha = body.get("fecha") or date.today().isoformat()
    hora_inicio = str(body.get("hora_inicio","")).strip()
    hora_fin = str(body.get("hora_fin","")).strip()
    
    # Validaciones de montos
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

    # Obtener todos los viajes para calcular duplicados y número
    all_trips = ws_trips.get_all_records()

    # Prevención de duplicados
    for r in all_trips:
        if str(r.get("Fecha")) == str(fecha) and str(r.get("Hora inicio")) == hora_inicio and str(r.get("Hora fin")) == hora_fin:
            return jsonify({"error":"duplicate"}), 409

    # Cálculo del número de viaje
    same_date_count = sum(1 for r in all_trips if str(r.get("Fecha")) == str(fecha))
    numero = same_date_count + 1

    # 1. Registrar el nuevo viaje
    row = [fecha, numero, hora_inicio, hora_fin, monto, propina, aeropuerto_val, total]
    ws_trips.append_row(row)
    app.logger.info(f"New trip appended: {row}")
    
    # 2. Recalcular y actualizar el bono del día
    # Volver a obtener la lista para asegurar que el registro POST esté incluido en el cálculo del bono
    all_trips_after_post = ws_trips.get_all_records()
    trips_today = [r for r in all_trips_after_post if str(r.get("Fecha")) == str(fecha)]
    
    current_bonus = calculate_current_bonus(trips_today)
    update_daily_bonus_sheet(client, fecha, current_bonus)
    
    # Respuesta
    return jsonify({"status":"ok","trip":dict(zip(TRIPS_HEADERS,row)), "new_bonus": current_bonus}), 201

# app.py (Nueva ruta)

@app.route("/api/expenses", methods=["GET", "POST"])
def api_expenses():
    """
    GET: optional ?date=YYYY-MM-DD returns expenses for that date (defaults to today)
    POST: JSON with keys: fecha (optional), hora (optional), monto, categoria, descripcion
    """
    # 1. Autenticación
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    client = get_gspread_client()
    ws_gastos = ensure_sheet_with_headers(client, GASTOS_WS_NAME, GASTOS_HEADERS)

    # --- Lógica GET (Recuperar Gastos del Día) ---
    if request.method == "GET":
        qdate = request.args.get("date") or date.today().isoformat()
        
        all_expenses = ws_gastos.get_all_records()
        filtered_expenses = [r for r in all_expenses if str(r.get("Fecha")) == str(qdate)]
        
        return jsonify(filtered_expenses)

    # --- Lógica POST (Registrar Nuevo Gasto) ---
    
    body = request.get_json() or {}
    
    # Recolección de datos, con valores por defecto
    fecha = body.get("fecha") or date.today().isoformat()
    hora = body.get("hora") or datetime.now().strftime('%H:%M')
    categoria = str(body.get("categoria", "")).strip()
    descripcion = str(body.get("descripcion", "")).strip()
    
    # Validación del Monto
    try:
        monto = float(body.get("monto", 0))
        if monto <= 0:
            return jsonify({"error": "monto_invalido", "message": "El monto debe ser un valor positivo."}), 400
    except Exception:
        return jsonify({"error": "monto_invalido", "message": "El monto debe ser numérico."}), 400

    # 3. Registrar el nuevo gasto
    row = [fecha, hora, monto, categoria, descripcion]
    ws_gastos.append_row(row)
    app.logger.info(f"New expense appended: {row}")
    
    # 4. Respuesta
    return jsonify({"status":"ok", "expense": dict(zip(GASTOS_HEADERS, row))}), 201



# ----------------------------
# API: Extras (similar but no propina/aeropuerto)
# ----------------------------
@app.route("/api/extras", methods=["GET","POST"])
def api_extras():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    client = get_gspread_client()
    headers = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Total"]
    ws = ensure_sheet_with_headers(client, "TripCounter_Extras", headers)
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

    # Prevent duplicates
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
    return jsonify({"status":"ok","extra":dict(zip(headers,row))}), 201

# ----------------------------
# API: Presupuesto (create/list/mark paid)
# ----------------------------
@app.route("/api/presupuesto", methods=["GET","POST","PUT"])
def api_presupuesto():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    client = get_gspread_client()
    headers = ["alias","categoria","monto","fecha_pago","pagado"]
    ws = ensure_sheet_with_headers(client, "TripCounter_Presupuesto", headers)

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
        row = [alias, categoria, monto, fecha_pago, "False"]
        ws.append_row(row)
        return jsonify({"status":"ok","entry":dict(zip(headers,row))}), 201

    # PUT -> mark as paid; expects 'row_index' (1-based)
    if request.method == "PUT":
        body = request.get_json() or {}
        row_index = body.get("row_index")
        if not row_index:
            return jsonify({"error":"missing_row_index"}), 400
        try:
            # set pagado column (5th) to True for given row
            ws.update_cell(int(row_index), 5, "True")
            return jsonify({"status":"ok"}), 200
        except Exception as e:
            return jsonify({"error":str(e)}), 500

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    print("DEBUG: Flask app ejecutándose directamente")
    #app.run(host="0.0.0.0", port=10000, debug=True)#