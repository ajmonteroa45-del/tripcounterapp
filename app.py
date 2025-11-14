import os
import json
import logging
import sys
# Importamos traceback para usarlo en la función de depuración de errores
import traceback
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from requests_oauthlib import OAuth2Session
from google.oauth2 import service_account
import gspread
import base64
from google.oauth2.service_account import Credentials
import gspread.exceptions

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
TRIPS_WS_NAME = "TripCounter_Trips"
TRIPS_HEADERS = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Propina","Aeropuerto","Total"]
BONUS_WS_NAME = "TripCounter_Bonuses"
BONUS_HEADERS = ["Fecha", "Bono total"]
BONUS_RULES = {
    'LUN_JUE': {13: 16, 17: 9, 21: 12, 25: 16},
    'VIE_SAB': {13: 15, 17: 10, 21: 13, 25: 15},
    'DOM': {12: 14, 16: 10, 19: 11, 23: 14},
}
GASTOS_WS_NAME = "TripCounter_Gastos"
GASTOS_HEADERS = ["Fecha", "Hora", "Monto", "Categoría", "Descripción"]
PRESUPUESTO_WS_NAME = "TripCounter_Presupuesto"
PRESUPUESTO_HEADERS = ["alias", "categoria", "monto", "fecha_pago", "pagado"] 
EXTRAS_WS_NAME = "TripCounter_Extras"
EXTRAS_HEADERS = ["Fecha","Numero","Hora inicio","Hora fin","Monto","Total"]
KM_WS_NAME = "TripCounter_Kilometraje"
KM_HEADERS = ["Fecha", "KM Inicio", "KM Fin", "Recorrido", "Notas"]
SUMMARIES_WS_NAME = "TripCounter_Summaries"
SUMMARIES_HEADERS = [
    "Fecha",
    "Mes",
    "Año",
    "KM Recorrido",
    "Viajes Totales",
    "Ingreso Bruto",
    "Bono Total",
    "Gasto Total",
    "Ganancia Neta",
    "Productividad S/KM"
]

# ----------------------------
# Debug inicial visible en Render logs
# ----------------------------
@app.before_request
def startup_debug():
    """Imprime variables de entorno clave solo una vez."""
    if not getattr(app, "_startup_debug_done", False):
        print("⚙️ DEBUG desde Flask startup:")
        for key in ["GSPREAD_CLIENT_EMAIL", "FLASK_SECRET_KEY", "OAUTH_CLIENT_ID"]:
            print(f"{key}: {'✅ OK' if os.getenv(key) else '❌ MISSING'}")
        app._startup_debug_done = True

# ----------------------------
# Google Sheets Client & Utilitarios
# ----------------------------
def get_gspread_client():
    """
    Establece la conexión con Google Sheets reconstruyendo el JSON
    a partir de variables de entorno individuales (GSPREAD_*).
    """
    # 1. Verificar la existencia de las variables clave
    if not os.getenv("GSPREAD_PRIVATE_KEY") or not os.getenv("GSPREAD_CLIENT_EMAIL"):
        app.logger.error("❌ ERROR CRÍTICO DE CREDENCIALES: Faltan variables GSPREAD_PRIVATE_KEY o GSPREAD_CLIENT_EMAIL.")
        raise Exception("Error de configuración: Faltan variables de credenciales GSPREAD.")

    try:
        # 2. Reconstruir el diccionario de credenciales
        private_key = os.getenv("GSPREAD_PRIVATE_KEY")
        # Esto maneja el caso de que los saltos de línea se hayan copiado como caracteres literales '\n'
        cleaned_private_key = private_key.replace("\\n", "\n") 
        
        creds_dict = {
            "type": os.getenv("GSPREAD_TYPE", "service_account"),
            "project_id": os.getenv("GSPREAD_PROJECT_ID"),
            "private_key_id": os.getenv("GSPREAD_PRIVATE_KEY_ID"),
            "private_key": cleaned_private_key, 
            "client_email": os.getenv("GSPREAD_CLIENT_EMAIL"),
            "client_id": os.getenv("GSPREAD_CLIENT_ID"),
            "auth_uri": os.getenv("GSPREAD_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": os.getenv("GSPREAD_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": os.getenv("GSPREAD_AUTH_CERT_URL"),
            "client_x509_cert_url": os.getenv("GSPREAD_CLIENT_CERT_URL"),
        }
        
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file"
            ]
        )

        client = gspread.authorize(credentials)
        return client
    
    except Exception as e:
        app.logger.error(f"❌ ERROR CRÍTICO DE CREDENCIALES: Falló la reconstrucción o autorización. Detalle: {e}")
        raise Exception(f"Error de credenciales GSheets: {e}")


def ensure_sheet_with_headers(client, ws_name, headers):
    """
    Abre el Workbook (archivo) con el nombre 'ws_name' y asegura las cabeceras.
    """
    WORKBOOK_NAME = ws_name 
    try:
        # 1. Abrir el Workbook (Archivo principal de Google Sheets)
        workbook = client.open(WORKBOOK_NAME) 
    except gspread.WorksheetNotFound:
        # Este error ocurre si el archivo con ese nombre no existe o la cuenta de servicio no tiene acceso
        app.logger.error(f"❌ ERROR: El archivo principal '{WORKBOOK_NAME}' no fue encontrado. Verifica el acceso de la Cuenta de Servicio.")
        raise gspread.WorksheetNotFound(f"Archivo '{WORKBOOK_NAME}' no encontrado o sin permisos.")
        
    # 2. Obtener la Pestaña (Worksheet)
    ws = workbook.get_worksheet(0)
        
    # 3. Asegurar que las Cabeceras son correctas
    try:
        current_headers = ws.row_values(1)
        if current_headers != headers:
            app.logger.warning(f"⚠️ Las cabeceras de '{WORKBOOK_NAME}' no coinciden. Sobrescribiendo.")
            ws.delete_rows(1)
            ws.insert_row(headers, 1)
    except Exception as e:
        app.logger.error(f"Error al verificar cabeceras en {WORKBOOK_NAME}: {e}")
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

def calculate_daily_summary(client, target_date):
    """
    Calcula los totales de Ingresos, Egresos y Kilometraje para una fecha dada.
    target_date debe ser un string en formato YYYY-MM-DD.
    """
    # 1. Obtener datos de Viajes e Ingresos (Trips)
    ws_trips = ensure_sheet_with_headers(client, TRIPS_WS_NAME, TRIPS_HEADERS)
    trips_records = ws_trips.get_all_records()
    trips_today = [r for r in trips_records if str(r.get("Fecha")) == str(target_date)]
    
    total_gross_income = sum(float(r.get("Total", 0)) for r in trips_today)
    num_trips = len(trips_today)

    # 2. Obtener datos de Gastos
    ws_gastos = ensure_sheet_with_headers(client, GASTOS_WS_NAME, GASTOS_HEADERS)
    gastos_records = ws_gastos.get_all_records()
    gastos_today = [r for r in gastos_records if str(r.get("Fecha")) == str(target_date)]
    
    total_expenses = sum(float(r.get("Monto", 0)) for r in gastos_today)

    # 3. Obtener datos de Kilometraje
    ws_km = ensure_sheet_with_headers(client, KM_WS_NAME, KM_HEADERS)
    km_records = ws_km.get_all_records()
    km_record = next((r for r in km_records if str(r.get("Fecha")) == str(target_date)), None)
    
    total_km_recorrido = int(km_record.get("Recorrido", 0)) if km_record and km_record.get("Recorrido") else 0

    # 4. Calcular el Ingreso Neto y la Productividad
    
    # Bono del día
    ws_bonuses = ensure_sheet_with_headers(client, BONUS_WS_NAME, BONUS_HEADERS)
    bonus_records = ws_bonuses.get_all_records()
    current_bonus = next((float(r.get('Bono total', 0.0)) for r in bonus_records if str(r.get("Fecha")) == str(target_date)), 0.0)

    # Ingreso total (Viajes + Bono)
    total_income = total_gross_income + current_bonus
    
    # Ingreso Neto: (Ingreso Total - Gastos)
    net_income = total_income - total_expenses
    
    # Productividad (Soles por KM): Si hay KM recorrido, dividimos
    productivity_per_km = net_income / total_km_recorrido if total_km_recorrido > 0 else 0.0
    
    return {
        "fecha": target_date,
        "num_trips": num_trips,
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_income": round(net_income, 2),
        "total_km": total_km_recorrido,
        "current_bonus": round(current_bonus, 2),
        "productivity_per_km": round(productivity_per_km, 2),
        "is_complete": num_trips > 0 and total_km_recorrido > 0
    }


# ----------------------------
# ROUTES: Auth
# ----------------------------
@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        app.logger.error("❌ OAUTH env vars not configured.")
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
        
        userinfo = oauth.get("https://www.googleapis.com/oauth2/v2/userinfo").json()
        session['email'] = userinfo.get('email')
        app.logger.info(f"User logged in: {session.get('email')}")
        
        # --- LÓGICA DE VERIFICACIÓN DE NUEVO USUARIO ---
        client = get_gspread_client()
        ws_pres = ensure_sheet_with_headers(client, PRESUPUESTO_WS_NAME, PRESUPUESTO_HEADERS)
        
        email_to_check = session.get('email')
        is_new_user = False
        
        try:
            ws_pres.find(email_to_check)
        except gspread.exceptions.CellNotFound:
            is_new_user = True
        except Exception as e:
            app.logger.error(f"Error al verificar existencia de usuario: {e}")
            is_new_user = False 

        if is_new_user:
            app.logger.info(f"Nuevo usuario {email_to_check} detectado. Redirigiendo a Presupuesto.")
            flash('¡Bienvenido/a! Por favor, agrega tus primeros ítems de presupuesto para empezar.', 'success')
            return redirect(url_for("presupuesto_page"))

        return redirect(url_for("index"))

    except Exception as e:
        # --- MODIFICACIÓN DE DEBUGGING AQUÍ ---
        app.logger.error(f"❌ ERROR CRÍTICO en OAuth callback: {e}")
        app.logger.error("Se produjo una excepción después del login de Google. Imprimiendo Stack Trace completo:")
        app.logger.error(traceback.format_exc()) # Imprime el stack trace completo al log
        # --------------------------------------
        return f"<h3>Authentication failed. Check logs for GSheets credential error. Detail: {e}</h3>", 500


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
    if not email:
        return render_template("login.html")
    
    reminders = []
    
    try:
        # A. Intentar conectar con GSheets
        client = get_gspread_client()
        
        # B. Intentar cargar los recordatorios
        try:
            ws_pres = ensure_sheet_with_headers(client, PRESUPUESTO_WS_NAME, PRESUPUESTO_HEADERS)
            records = ws_pres.get_all_records()
            
            today = date.today()
            
            for i, r in enumerate(records):
                try:
                    date_str = r.get("fecha_pago")
                    if not date_str or not date_str.strip():
                        continue 
                        
                    fp = datetime.strptime(date_str, "%Y-%m-%d").date()
                    
                except Exception:
                    continue
                
                days_left = (fp - today).days
                
                if str(r.get("pagado")).lower() == "true":
                    continue
                
                reminder_data = {
                    "categoria": r.get("categoria"),
                    "monto": r.get("monto"),
                    "row_index": i + 2
                }
                
                if days_left == 3:
                    reminder_data["type"] = "3days"
                    reminders.append(reminder_data)
                elif days_left == 0:
                    reminder_data["type"] = "due"
                    reminders.append(reminder_data)
                    
        except Exception as e:
            app.logger.error(f"❌ Error cargando recordatorios desde la hoja: {e}")
            flash(f'⚠️ Error al cargar los recordatorios: {e}', 'warning')

    except Exception as e:
        app.logger.error(f"❌ Error CRÍTICO conectando a GSheets/Credenciales: {e}")
        flash('🛑 Error de conexión a Google Sheets. Los datos pueden estar incompletos. Revisa tus variables GSPREAD.', 'danger')
        reminders = []

    return render_template("home.html", email=email, reminders=reminders)


@app.route("/viajes")
def viajes_page():
    if not session.get('email'):
        return redirect(url_for("login"))
    return render_template("trips.html", email=session.get('email'))

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

    try:
        client = get_gspread_client()
        ws_trips = ensure_sheet_with_headers(client, TRIPS_WS_NAME, TRIPS_HEADERS)
        ws_bonuses = ensure_sheet_with_headers(client, BONUS_WS_NAME, BONUS_HEADERS)
    except Exception as e:
        app.logger.error(f"Error en API Trips al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500


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

    try:
        row = [fecha, numero, hora_inicio, hora_fin, monto, propina, aeropuerto_val, total]
        ws_trips.append_row(row)
        app.logger.info(f"New trip appended: {row}")
        
        all_trips_after_post = ws_trips.get_all_records()
        trips_today = [r for r in all_trips_after_post if str(r.get("Fecha")) == str(fecha)]
        
        current_bonus = calculate_current_bonus(trips_today)
        update_daily_bonus_sheet(client, fecha, current_bonus)
    except Exception as e:
        app.logger.error(f"Error al registrar viaje o actualizar bono: {e}")
        return jsonify({"error": "Error interno al interactuar con Sheets."}), 500
    
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

    try:
        client = get_gspread_client()
        ws_gastos = ensure_sheet_with_headers(client, GASTOS_WS_NAME, GASTOS_HEADERS)
    except Exception as e:
        app.logger.error(f"Error en API Expenses al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500

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

    try:
        row = [fecha, hora, monto, categoria, descripcion]
        ws_gastos.append_row(row)
        app.logger.info(f"New expense appended: {row}")
    except Exception as e:
        app.logger.error(f"Error al registrar gasto: {e}")
        return jsonify({"error": "Error interno al interactuar con Sheets."}), 500
    
    return jsonify({"status":"ok", "expense": dict(zip(GASTOS_HEADERS, row))}), 201


# ----------------------------
# API: Extras
# ----------------------------
@app.route("/api/extras", methods=["GET","POST"])
def api_extras():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    try:
        client = get_gspread_client()
        ws = ensure_sheet_with_headers(client, EXTRAS_WS_NAME, EXTRAS_HEADERS)
    except Exception as e:
        app.logger.error(f"Error en API Extras al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500

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

    try:
        row = [fecha, numero, hi, hf, monto, total]
        ws.append_row(row)
        app.logger.info(f"New extra appended: {row}")
    except Exception as e:
        app.logger.error(f"Error al registrar extra: {e}")
        return jsonify({"error": "Error interno al interactuar con Sheets."}), 500
    
    return jsonify({"status":"ok","extra":dict(zip(EXTRAS_HEADERS,row))}), 201

# ----------------------------
# API: Presupuesto
# ----------------------------
@app.route("/api/presupuesto", methods=["GET","POST","PUT"])
def api_presupuesto():
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401
    
    try:
        client = get_gspread_client()
        ws = ensure_sheet_with_headers(client, PRESUPUESTO_WS_NAME, PRESUPUESTO_HEADERS)
    except Exception as e:
        app.logger.error(f"Error en API Presupuesto al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500


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
        
        try:
            monto = float(monto)
            if monto <= 0:
                 return jsonify({"error": "monto_invalido", "message": "El monto debe ser un valor positivo."}), 400
        except Exception:
            return jsonify({"error": "monto_invalido", "message": "El monto debe ser numérico."}), 400

        try:
            row = [alias, categoria, monto, fecha_pago, "False"]
            ws.append_row(row)
        except Exception as e:
            app.logger.error(f"Error al registrar presupuesto: {e}")
            return jsonify({"error": "Error interno al interactuar con Sheets."}), 500
            
        return jsonify({"status":"ok","entry":dict(zip(PRESUPUESTO_HEADERS,row))}), 201

    # PUT -> mark as paid; expects 'row_index' (1-based)
    if request.method == "PUT":
        body = request.get_json() or {}
        row_index = body.get("row_index")
        if not row_index:
            return jsonify({"error":"missing_row_index"}), 400
        try:
            ws.update_cell(int(row_index), PRESUPUESTO_HEADERS.index("pagado") + 1, "True")
            return jsonify({"status":"ok"}), 200
        except Exception as e:
            app.logger.error(f"Error actualizando celda en GSheets: {e}")
            return jsonify({"error":f"Error al actualizar la hoja: {e}"}), 500

# ----------------------------
# API: Kilometraje
# ----------------------------
@app.route("/api/kilometraje", methods=["GET", "POST"])
def api_kilometraje():
    """
    POST: Registra el KM de inicio O actualiza el KM de fin para el día.
    GET: Devuelve el registro de kilometraje del día.
    """
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    try:
        client = get_gspread_client()
        ws = ensure_sheet_with_headers(client, KM_WS_NAME, KM_HEADERS)
    except Exception as e:
        app.logger.error(f"Error en API Kilometraje al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500
        
    qdate = request.args.get("date") or date.today().isoformat()
    all_records = ws.get_all_records()
    
    existing_record_index = -1
    for i, r in enumerate(all_records):
        if str(r.get("Fecha")) == str(qdate):
            existing_record_index = i + 2 
            break

    # --- Lógica GET (Visualizar) ---
    if request.method == "GET":
        if existing_record_index > 0:
            return jsonify(all_records[existing_record_index - 2]) 
        else:
            return jsonify({"status": "no_record", "message": "No hay registro de kilometraje para este día."}), 200

    # --- Lógica POST (Registrar/Actualizar) ---
    body = request.get_json() or {}
    
    km_value = body.get("km_value")
    action = body.get("action")
    notes = body.get("notas", "")
    
    try:
        km_value = int(km_value)
    except Exception:
        return jsonify({"error": "km_invalido", "message": "El valor del kilometraje debe ser un número entero."}), 400

    try:
        if action == 'start':
            if existing_record_index > 0:
                return jsonify({"error": "ya_iniciado", "message": "La jornada de hoy ya tiene un KM de inicio registrado."}), 409
            
            row = [qdate, km_value, "", "", notes] 
            ws.append_row(row)
            return jsonify({"status": "start_recorded", "km_inicio": km_value}), 201

        elif action == 'end':
            if existing_record_index == -1:
                return jsonify({"error": "no_iniciado", "message": "No se puede finalizar sin un KM de inicio."}), 400
            
            current_record = all_records[existing_record_index - 2]
            km_inicio = int(current_record.get("KM Inicio", 0))
            km_fin = km_value
            
            if km_fin < km_inicio:
                return jsonify({"error": "km_invalido", "message": "El KM final no puede ser menor que el KM de inicio."}), 400

            recorrido = km_fin - km_inicio
            
            KM_FIN_COL = KM_HEADERS.index("KM Fin") + 1
            RECORRIDO_COL = KM_HEADERS.index("Recorrido") + 1
            
            ws.update_cell(existing_record_index, KM_FIN_COL, km_fin)
            ws.update_cell(existing_record_index, RECORRIDO_COL, recorrido)
            
            return jsonify({"status": "end_recorded", "km_fin": km_fin, "recorrido": recorrido}), 200

        else:
            return jsonify({"error": "accion_invalida", "message": "La acción debe ser 'start' o 'end'."}), 400
    except Exception as e:
        app.logger.error(f"Error al registrar o actualizar kilometraje: {e}")
        return jsonify({"error": "Error interno al interactuar con Sheets."}), 500


# ----------------------------
# API: Resumen Mensual
# ----------------------------
@app.route("/api/summary", methods=["GET"])
def api_summary():
    """
    GET: optional ?date=YYYY-MM-DD returns the productivity summary for that day.
    """
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    target_date = request.args.get("date") or date.today().isoformat()
    
    try:
        client = get_gspread_client()
        summary_data = calculate_daily_summary(client, target_date)
        return jsonify(summary_data)
    except Exception as e:
        app.logger.error(f"Error generando resumen: {e}")
        return jsonify({"error": "Error interno al calcular el resumen."}), 500

# ----------------------------
# API: Reporte Mensual
# ----------------------------
@app.route("/api/monthly_report", methods=["GET"])
def api_monthly_report():
    """
    GET: Requiere ?month=MM&year=YYYY. Calcula el reporte del mes y lo guarda en TripCounter_Summaries.
    """
    if not session.get('email'):
        return jsonify({"error":"not_authenticated"}), 401

    month = request.args.get("month")
    year = request.args.get("year")
    
    if not month or not year:
        return jsonify({"error": "missing_fields", "message": "Faltan los parámetros 'month' y 'year'."}), 400
        
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        return jsonify({"error": "invalid_format", "message": "Month y Year deben ser números."}), 400

    try:
        client = get_gspread_client()
    except Exception as e:
        app.logger.error(f"Error en API Reporte Mensual al conectar a GSheets: {e}")
        return jsonify({"error": f"Error de conexión a la base de datos: {e}"}), 500
    
    # 1. Determinar el rango de fechas del mes
    try:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    except ValueError:
        return jsonify({"error": "invalid_date", "message": "Mes o año inválido."}), 400

    # 2. Iterar por cada día del mes y consolidar datos
    monthly_summary = {
        "month": month,
        "year": year,
        "total_km": 0.0,
        "total_trips": 0,
        "total_gross_income": 0.0, 
        "total_bonus": 0.0,
        "total_expenses": 0.0,
        "net_income": 0.0,
    }
    
    current_date = start_date
    daily_data = [] 
    
    while current_date <= end_date:
        date_str = current_date.isoformat()
        try:
            day_summary = calculate_daily_summary(client, date_str)
            
            # Sumar al resumen mensual
            monthly_summary["total_km"] += day_summary["total_km"]
            monthly_summary["total_trips"] += day_summary["num_trips"]
            monthly_summary["total_gross_income"] += day_summary["total_income"] 
            monthly_summary["total_expenses"] += day_summary["total_expenses"]
            monthly_summary["total_bonus"] += day_summary["current_bonus"]
            
            daily_data.append(day_summary)

        except Exception as e:
            app.logger.warning(f"Error procesando el día {date_str}: {e}")
            pass
            
        current_date += timedelta(days=1)

    # 3. Cálculo Final y Productividad Mensual
    monthly_summary["net_income"] = monthly_summary["total_gross_income"] - monthly_summary["total_expenses"]
    
    total_income_with_bonus = monthly_summary["total_gross_income"]
    
    productivity_per_km = monthly_summary["net_income"] / monthly_summary["total_km"] if monthly_summary["total_km"] > 0 else 0.0
    
    monthly_summary["productivity_per_km"] = round(productivity_per_km, 2)
    
    # 4. Guardar en TripCounter_Summaries (Histórico)
    try:
        ws_summaries = ensure_sheet_with_headers(client, SUMMARIES_WS_NAME, SUMMARIES_HEADERS)
        summary_date_str = start_date.isoformat()
        
        records = ws_summaries.get_all_records()
        
        existing_row_index = -1
        for i, r in enumerate(records):
            if str(r.get("Mes")) == str(month) and str(r.get("Año")) == str(year):
                existing_row_index = i + 2 
                break
        
        row_data = [
            summary_date_str,
            month,
            year,
            monthly_summary["total_km"],
            monthly_summary["total_trips"],
            round(total_income_with_bonus, 2),
            round(monthly_summary["total_bonus"], 2), 
            round(monthly_summary["total_expenses"], 2),
            round(monthly_summary["net_income"], 2),
            productivity_per_km
        ]
        
        if existing_row_index > 0:
            ws_summaries.update(f'A{existing_row_index}', [row_data])
            app.logger.info(f"Reporte mensual actualizado para {month}/{year}")
        else:
            ws_summaries.append_row(row_data)
            app.logger.info(f"Reporte mensual guardado para {month}/{year}")

    except Exception as e:
        app.logger.error(f"Error al guardar el resumen en Sheets: {e}")
        monthly_summary["save_error"] = str(e)


    # 5. Devolver el reporte al Frontend
    return jsonify({"report": monthly_summary, "details": daily_data}), 200


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    print("DEBUG: Flask app ejecutándose directamente")
    # Para ejecutar localmente, descomentar la siguiente línea
    # app.run(host="0.0.0.0", port=10000, debug=True)
