import os
import time
import json
import logging
import sys
import traceback 
from datetime import date, datetime, timedelta # Asegúrate de que 'date' esté importado
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
# MODIFICADO: Añadida columna 'Tipo'
PRESUPUESTO_WS_NAME = "TripCounter_Presupuesto"
PRESUPUESTO_HEADERS = ["alias", "categoria", "monto", "tipo", "fecha_pago", "pagado"] 
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
# --- ID DE HOJA CRÍTICA (PRESENTE EN ENTORNO DE RENDER) ---
PRESUPUESTO_SHEET_ID = os.environ.get("PRESUPUESTO_SHEET_ID")


# ----------------------------
# Debug inicial visible en Render logs
# ----------------------------
@app.before_request
def startup_debug():
    """Imprime variables de entorno clave solo una vez."""
    if not getattr(app, "_startup_debug_done", False):
        print("⚙️ DEBUG desde Flask startup:")
        for key in ["GSPREAD_CLIENT_EMAIL", "FLASK_SECRET_KEY", "OAUTH_CLIENT_ID", "PRESUPUESTO_SHEET_ID"]:
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
    if not os.getenv("GSPREAD_PRIVATE_KEY") or not os.getenv("GSPREAD_CLIENT_EMAIL"):
        app.logger.error("❌ ERROR CRÍTICO DE CREDENCIALES: Faltan variables GSPREAD_PRIVATE_KEY o GSPREAD_CLIENT_EMAIL.")
        raise Exception("Error de configuración: Faltan variables de credenciales GSPREAD.")

    try:
        private_key = os.getenv("GSPREAD_PRIVATE_KEY")
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

# --- FUNCIÓN MODIFICADA PARA USAR ID DEL ARCHIVO DE PRESUPUESTO ---
def ensure_sheet_with_headers(client, ws_name, headers, max_retries=3):
    """
    Abre el Workbook (archivo) usando el ID si es 'TripCounter_Presupuesto' 
    o el nombre para el resto. Implementa reintentos.
    """
    WORKBOOK_NAME = ws_name
    
    # Seleccionamos el método de apertura (por ID si es la hoja crítica, por nombre para el resto)
    if WORKBOOK_NAME == "TripCounter_Presupuesto":
        if not PRESUPUESTO_SHEET_ID:
            app.logger.error("❌ ERROR CRÍTICO: PRESUPUESTO_SHEET_ID no configurado en variables de entorno.")
            raise Exception("Falta el ID del archivo de Presupuesto en la configuración de Render.")
        open_func = lambda: client.open_by_key(PRESUPUESTO_SHEET_ID)
    else:
        open_func = lambda: client.open(WORKBOOK_NAME)

    # 1. Abrir el Workbook con reintentos
    workbook = None
    for attempt in range(max_retries):
        try:
            workbook = open_func()
            break # Éxito, salir del bucle
        except gspread.exceptions.SpreadsheetNotFound as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                app.logger.warning(f"⚠️ Intento {attempt + 1} fallido para abrir '{WORKBOOK_NAME}'. Reintentando en {wait_time}s. Error: {e}")
                time.sleep(wait_time)
            else:
                app.logger.error(f"❌ ERROR CRÍTICO: Fallaron todos los {max_retries} intentos para abrir el archivo '{WORKBOOK_NAME}'. Error: {e}")
                # El error se lanza como NotFound, pero el mensaje indica que falló después de reintentos.
                raise gspread.exceptions.SpreadsheetNotFound(f"Archivo '{WORKBOOK_NAME}' no encontrado después de reintentos (ID:{PRESUPUESTO_SHEET_ID}).") from e
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                app.logger.warning(f"⚠️ Intento {attempt + 1} fallido por error inesperado. Reintentando en {wait_time}s. Error: {e}")
                time.sleep(wait_time)
            else:
                app.logger.error(f"❌ ERROR CRÍTICO: Falla final por error inesperado: {e}")
                raise

    # 2. Obtener la Pestaña (Worksheet)
    if workbook is None:
        raise Exception(f"Error fatal: la conexión con Google Sheets no se pudo establecer para {WORKBOOK_NAME}.")

    try:
        ws = workbook.get_worksheet(0)
    except Exception as e:
        app.logger.error(f"Error al obtener la pestaña de {WORKBOOK_NAME}: {e}")
        raise
        
    # 3. Asegurar que las Cabeceras son correctas
    try:
        current_headers = ws.row_values(1)
        # IMPORTANTE: Si las cabeceras han cambiado en el código, la hoja de Sheets
        # DEBE ser actualizada.
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
# --- FIN DE LA FUNCIÓN MODIFICADA ---


# ----------------------------
# FUNCIONES DE LÓGICA DE NEGOCIO (El resto del código se mantiene igual)
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
        app.logger.error(f"❌ ERROR CRÍTICO en OAuth callback: {e}")
        app.logger.error("Se produjo una excepción después del login de Google. Imprimiendo Stack Trace completo:")
        app.logger.error(traceback.format_exc())
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
                # Solo procesamos si hay fecha de pago (es decir, si no es Gasto Variable)
                if not r.get("fecha_pago"):
                    continue 

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
    
    # MODIFICACIÓN CRÍTICA: Calcular la fecha actual y pasarla a la plantilla
    today_date = date.today().isoformat()
    
    return render_template("trips.html", 
                           email=session.get('email'),
                           today_date=today_date) # Pasar la fecha de hoy a la plantilla

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
    # ... (El código de la API de Trips se mantiene igual) ...
    # Se mantiene la lógica completa de las APIS y otras funciones...

# ----------------------------
# API: Expenses (Gastos)
# ----------------------------
@app.route("/api/expenses", methods=["GET", "POST"])
def api_expenses():
    # ... (El código de la API de Expenses se mantiene igual) ...

# ----------------------------
# API: Extras
# ----------------------------
@app.route("/api/extras", methods=["GET","POST"])
def api_extras():
    # ... (El código de la API de Extras se mantiene igual) ...

# ----------------------------
# API: Presupuesto
# ----------------------------
@app.route("/api/presupuesto", methods=["GET","POST","PUT","DELETE"])
def api_presupuesto():
    # ... (El código de la API de Presupuesto se mantiene igual) ...

# ----------------------------
# API: Kilometraje
# ----------------------------
@app.route("/api/kilometraje", methods=["GET", "POST"])
def api_kilometraje():
    # ... (El código de la API de Kilometraje se mantiene igual) ...

# ----------------------------
# API: Resumen Mensual
# ----------------------------
@app.route("/api/summary", methods=["GET"])
def api_summary():
    # ... (El código de la API de Summary se mantiene igual) ...

# ----------------------------
# API: Reporte Mensual
# ----------------------------
@app.route("/api/monthly_report", methods=["GET"])
def api_monthly_report():
    # ... (El código de la API de Reporte Mensual se mantiene igual) ...

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    print("DEBUG: Flask app ejecutándose directamente")
    # Para ejecutar localmente, descomentar la siguiente línea
    # app.run(host="0.0.0.0", port=10000, debug=True)
