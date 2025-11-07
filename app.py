## app.py - Trip Counter integrado (Flask) con Google OAuth + Google Sheets (presupuesto)
# Requisitos: flask, requests-oauthlib, pandas, matplotlib, pillow, gspread, google-auth
import os
import sys
import json
import logging
import base64
import re
from datetime import date, datetime
from io import BytesIO
from flask import Flask, redirect, url_for, session, request, render_template, send_file
from requests_oauthlib import OAuth2Session
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger("requests_oauthlib").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

# ---------- Environment / Config ----------
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
DEFAULT_REDIRECT = "https://tripcounter.online/oauth2callback"
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", DEFAULT_REDIRECT).strip()
if REDIRECT_URI.endswith("/"):
    REDIRECT_URI = REDIRECT_URI[:-1]

GSPREAD_SERVICE_ACCOUNT_JSON = os.environ.get("GSPREAD_SERVICE_ACCOUNT_JSON")
GSPREAD_PRESUPUESTO_SHEET_ID = os.environ.get("GSPREAD_PRESUPUESTO_SHEET_ID", "")

# ---------- Flask app ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = FLASK_SECRET_KEY or os.urandom(24)

BASE_DIR = os.path.join(os.getcwd(), "TripCounter_data")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(BASE_DIR, exist_ok=True)

BUTTON_COLOR = "#1034A6"

# OAuth constants
# app.py (Código Flask para Render)
from flask import Flask, redirect, url_for, session, request, render_template_string
import os, base64, json
from requests_oauthlib import OAuth2Session
from datetime import timedelta

# --- 1. CONFIGURACIÓN DE LA APLICACIÓN Y SECRETOS ---
# NOTA: En Render, estas variables se configuran como Environment Variables.
# Las leeremos desde variables de entorno.
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
REDIRECT_URI = "https://www.tripcounter.online/oauth2callback" # Render usa tu dominio final
# OAUTH URLS
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# ---------- Helpers ----------
def safe_alias_from_email(email: str) -> str:
    base = email.split("@")[0] if "@" in email else email
    return "".join(c for c in base if c.isalnum() or c in ("_", "-")).lower()

def user_csv_path(alias_email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(alias_email)}.csv")

def user_gastos_path(alias_email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(alias_email)}_gastos.csv")

def ensure_user_csv(alias_email: str) -> str:
    path = user_csv_path(alias_email)
    if not os.path.exists(path):
        df = pd.DataFrame(columns=["fecha","tipo","viaje_num","hora_inicio","hora_fin","ganancia_base","aeropuerto","propina","total_viaje"])
        df.to_csv(path, index=False)
    return path

def ensure_gastos_csv(alias_email: str) -> str:
    path = user_gastos_path(alias_email)
    if not os.path.exists(path):
        df = pd.DataFrame(columns=["fecha","concepto","monto"])
        df.to_csv(path, index=False)
    return path

def validate_time_string(t: str) -> bool:
    if not isinstance(t, str) or t.strip() == "":
        return False
    t = t.strip()
    if re.match(r'^[0-2]\d:[0-5]\d$', t):
        hh = int(t.split(":")[0])
        return 0 <= hh <= 23
    return False

def total_of_trips(rows) -> float:
    return sum(float(r.get("total_viaje", 0)) for r in rows)

# ---------- gspread (presupuesto) ----------
def get_gspread_client_from_env():
    if not GSPREAD_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GSPREAD_SERVICE_ACCOUNT_JSON not set in env.")
    try:
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON)
    except Exception:
        # try replace escaped newlines
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON.replace("\\n", "\n"))
    credentials = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.Client(auth=credentials)
    client.session = None
    return client

def load_presupuesto_gs():
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    client = get_gspread_client_from_env()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    df = pd.DataFrame(rows)
    for col in ["alias","categoria","monto","fecha_pago","pagado"]:
        if col not in df.columns:
            df[col] = ""
    return df[["alias","categoria","monto","fecha_pago","pagado"]]

def save_presupuesto_gs(df: pd.DataFrame):
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        return
    client = get_gspread_client_from_env()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    vals = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update(vals)

# ---------- imagenes / gráficos ----------
def generate_balance_image(rows, ingresos, gastos_total, combustible, neto, alias):
    labels = ["Ingresos (S/)", "Gastos (S/)", "Combustible (S/)", "Balance (S/)"]
    values = [round(float(ingresos),2), round(float(gastos_total),2), round(float(combustible),2), round(float(neto),2)]
    fig, ax = plt.subplots(figsize=(8,4.2))
    bars = ax.bar(labels, values, color=["#4da6ff", "#ff7f50", "#ff9f43", "#2ecc71"])
    ax.set_title(f"Balance {date.today().strftime('%Y-%m-%d')} — {alias}")
    top = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, val + top*0.02, f"{val}", ha="center", fontsize=9)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    # overlay logos optionally
    try:
        base_img = Image.open(buf).convert("RGBA")
        overlay = Image.new("RGBA", base_img.size)
        logo_path = os.path.join(IMAGES_DIR, "logo_app.png")
        uber_logo_path = os.path.join(IMAGES_DIR, "logo_uber.png")
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            w = int(base_img.width * 0.15)
            logo = logo.resize((w, int(logo.height*(w/logo.width))))
            overlay.paste(logo, (10,10), logo)
        if os.path.exists(uber_logo_path):
            ulogo = Image.open(uber_logo_path).convert("RGBA")
            w = int(base_img.width * 0.12)
            ulogo = ulogo.resize((w, int(ulogo.height*(w/ulogo.width))))
            overlay.paste(ulogo, (base_img.width - w - 10, 10), ulogo)
        combined = Image.alpha_composite(base_img, overlay)
        out_buf = BytesIO()
        combined.convert("RGB").save(out_buf, format="PNG")
        out_buf.seek(0)
        return out_buf
    except Exception:
        buf.seek(0)
        return buf

# ---------- OAuth endpoints ----------
@app.route('/login')
def login():
    app.logger.info(f"🔁 Iniciando login con redirect_uri: {REDIRECT_URI}")
    if not CLIENT_ID or not CLIENT_SECRET:
        app.logger.error("❌ CLIENT_ID o CLIENT_SECRET no están configurados.")
        return "<h3>Error: Faltan credenciales OAuth.</h3>", 500
    google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    authorization_url, state = google.authorization_url(AUTHORIZE_URL, access_type="offline", prompt="select_account")
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    if 'error' in request.args:
        return f"Google returned error: {request.args.get('error')}", 400
    google = OAuth2Session(CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
    token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.url)
    id_token_jwt = token.get('id_token')
    if id_token_jwt:
        try:
            payload_base64 = id_token_jwt.split('.')[1]
            padding = len(payload_base64) % 4
            payload_base64 += "=" * (4 - padding if padding else 0)
            payload = json.loads(base64.urlsafe_b64decode(payload_base64).decode())
            session['email'] = payload.get('email')
            session['oauth_token'] = token
            app.logger.info(f"✅ Usuario autenticado: {session['email']}")
        except Exception as e:
            app.logger.error("Error decoding id_token: " + str(e))
    return redirect(url_for('index'))

app = Flask(__name__)
# Necesitas una clave secreta para gestionar las sesiones de Flask
# **IMPORTANTE**: Cámbiala en Render por un valor largo y aleatorio.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "TU_CLAVE_SECRETA_POR_DEFECTO")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)


# --- 2. RUTAS DE INTERFAZ (Reemplazando st.XXX) ---

@app.route('/')
def home():
    # Verifica si el usuario está autenticado
    if 'email' in session:
        user_email = session['email']
        # --- CÓDIGO DE LA APLICACIÓN PRINCIPAL (AQUÍ DEBE IR TU LÓGICA DE TRIPS) ---
        return render_template_string("""
            <h1>Bienvenido a Trip Counter, {{ email }}</h1>
            <p>Aquí irá toda la lógica de tus pestañas (Uber/Didi, Gastos, etc.), reescrita sin Streamlit.</p>
            <a href="/logout"><button>Cerrar Sesión</button></a>
        """, email=user_email)
    else:
        # Página de inicio de sesión
        # ESTILOS: DEBES CREAR UN ARCHIVO CSS SEPARADO PARA TU IMAGEN DE FONDO
        return render_template_string("""
            <h1>Inicia Sesión para Acceder a Trip Counter</h1>
            <a href="/login"><button>Iniciar Sesión con Google</button></a>
            <p>Lee nuestra <a href="https://policy.tripcounter.online" target="_blank">Política de Privacidad</a>.</p>
        """)

# --- 3. LÓGICA DE OAUTH ---

@app.route('/login')
def login():
    # 1. Crea la sesión OAuth
    google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    # 2. Genera la URL de autorización de Google
    authorization_url, state = google.authorization_url(AUTHORIZE_URL, access_type="offline", prompt="select_account")
    session['oauth_state'] = state
    # 3. Redirige al usuario a Google
    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # 1. Recupera la sesión OAuth
    google = OAuth2Session(CLIENT_ID, state=session['oauth_state'], redirect_uri=REDIRECT_URI)
    
    try:
        # 2. Obtiene el token usando el código de la URL
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, 
                                   authorization_response=request.url)
        
        # 3. Obtiene la información del usuario (requiere decodificación del ID token)
        id_token_jwt = token.get('id_token')
        if id_token_jwt:
            # El token JWT debe ser decodificado para obtener la info (email, etc.)
            import jwt
            # Google usa un formato específico para su JWKS (clave pública).
            # Para este ejemplo, solo decodificaremos la carga útil.
            # En producción, ¡DEBES validar el token usando las claves públicas de Google!
            
            # Decodificación simple del payload para fines de prueba (NO SEGURO PARA PRODUCCIÓN)
            payload = json.loads(base64.b64decode(id_token_jwt.split('.')[1] + '==').decode())
            
            session['email'] = payload.get('email')
            session['token'] = token
            
            return redirect(url_for('home'))
        
    except Exception as e:
        app.logger.error(f"Error en OAuth callback: {e}")
        return "Fallo de autenticación. Inténtalo de nuevo.", 400

@app.route('/logout')
def logout():
    session.clear()

    return redirect(url_for('index'))

# ---------- Pages / routes ----------
@app.route('/')
def index():
    email = session.get('email')
    return render_template('home.html', email=email, app_name="Trip Counter", button_color=BUTTON_COLOR)

@app.route('/trips', methods=['GET','POST'])
def trips():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_user_csv(alias)
    message = None
    if request.method == 'POST':
        hi = request.form.get('hi','').strip()
        hf = request.form.get('hf','').strip()
        gan = float(request.form.get('gan','0') or 0)
        aer = True if request.form.get('aer') == 'on' else False
        prop = float(request.form.get('prop','0') or 0)
        errors=[]
        if not validate_time_string(hi): errors.append("Hora inicio inválida")
        if not validate_time_string(hf): errors.append("Hora fin inválida")
        if errors:
            message = {"type":"error","text":"; ".join(errors)}
        else:
            aeropuerto_val = 6.5 if aer else 0.0
            total_v = round(float(gan) + aeropuerto_val + float(prop), 2)
            csvp = user_csv_path(alias)
            df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            viaje_num = len(df) + 1
            new = {
                "fecha": date.today().isoformat(),
                "tipo":"normal",
                "viaje_num": viaje_num,
                "hora_inicio": hi,
                "hora_fin": hf,
                "ganancia_base": float(gan),
                "aeropuerto": aeropuerto_val,
                "propina": float(prop),
                "total_viaje": total_v
            }
            pd.DataFrame([new]).to_csv(csvp, mode='a', header=not os.path.exists(csvp) or os.path.getsize(csvp)==0, index=False)
            message = {"type":"success","text":"Viaje agregado ✅"}
    csvp = user_csv_path(alias)
    df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
    df_today = df[df['fecha']==date.today().isoformat()] if not df.empty else pd.DataFrame()
    return render_template('trips.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/extras', methods=['GET','POST'])
def extras():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_user_csv(alias)
    message=None
    if request.method=='POST':
        hi = request.form.get('hi','').strip()
        hf = request.form.get('hf','').strip()
        gan = float(request.form.get('gan','0') or 0)
        aer = True if request.form.get('aer') == 'on' else False
        prop = float(request.form.get('prop','0') or 0)
        if not validate_time_string(hi) or not validate_time_string(hf):
            message={"type":"error","text":"Hora inválida"}
        else:
            aeropuerto_val = 6.5 if aer else 0.0
            total_v = round(float(gan) + aeropuerto_val + float(prop), 2)
            csvp = user_csv_path(alias)
            df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            viaje_num = len(df) + 1
            new = {
                "fecha": date.today().isoformat(),
                "tipo":"extra",
                "viaje_num": viaje_num,
                "hora_inicio": hi,
                "hora_fin": hf,
                "ganancia_base": float(gan),
                "aeropuerto": aeropuerto_val,
                "propina": float(prop),
                "total_viaje": total_v
            }
            pd.DataFrame([new]).to_csv(csvp, mode='a', header=not os.path.exists(csvp) or os.path.getsize(csvp)==0, index=False)
            message={"type":"success","text":"Viaje extra agregado ✅"}
    csvp = user_csv_path(alias)
    df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
    df_today = df[(df['fecha']==date.today().isoformat()) & (df['tipo']=='extra')] if not df.empty else pd.DataFrame()
    return render_template('extras.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/gastos', methods=['GET','POST'])
def gastos():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_gastos_csv(alias)
    message=None
    if request.method=='POST':
        concept = request.form.get('concept','').strip()
        monto = float(request.form.get('monto','0') or 0)
        if not concept or monto <= 0:
            message={"type":"error","text":"Concepto vacío o monto inválido"}
        else:
            gastos_p = user_gastos_path(alias)
            new = {"fecha": date.today().isoformat(), "concepto": concept, "monto": monto}
            pd.DataFrame([new]).to_csv(gastos_p, mode='a', header=not os.path.exists(gastos_p) or os.path.getsize(gastos_p)==0, index=False)
            message={"type":"success","text":"Gasto agregado ✅"}
    gastos_p = user_gastos_path(alias)
    dfg = pd.read_csv(gastos_p) if os.path.exists(gastos_p) and os.path.getsize(gastos_p)>0 else pd.DataFrame()
    df_today = dfg[dfg['fecha']==date.today().isoformat()] if not dfg.empty else pd.DataFrame()
    return render_template('gastos.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/kilometraje', methods=['GET','POST'])
def kilometraje():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    message=None
    if request.method=='POST':
        combustible = float(request.form.get('combustible','0') or 0)
        km_final = float(request.form.get('km_final','0') or 0)
        if km_final <= 0:
            message={"type":"error","text":"Debes ingresar el kilometraje final."}
        else:
            csvp = ensure_user_csv(alias)
            df_all = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            df_today = df_all[df_all['fecha']==date.today().isoformat()] if not df_all.empty else pd.DataFrame()
            trips_rows = df_today.to_dict("records")
            gastos_path = ensure_gastos_csv(alias)
            gastos_rows = pd.read_csv(gastos_path).to_dict("records") if os.path.exists(gastos_path) and os.path.getsize(gastos_path)>0 else []
            ingresos = total_of_trips(trips_rows)
            gastos_total = sum(float(g.get("monto",0)) for g in gastos_rows)
            neto = round(float(ingresos) - float(gastos_total) - float(combustible), 2)
            summary = {"date": date.today().isoformat(), "total_viajes": len(trips_rows), "ingresos": ingresos, "gastos": gastos_total, "combustible": combustible, "kilometraje": km_final, "total_neto": neto}
            sum_path = os.path.join(BASE_DIR, f"{safe_alias_from_email(alias)}_summary_{date.today().isoformat()}.json")
            with open(sum_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            img_buf = generate_balance_image(trips_rows, ingresos, gastos_total, combustible, neto, alias)
            filename = os.path.join(IMAGES_DIR, f"{safe_alias_from_email(alias)}_{date.today().isoformat()}.png")
            with open(filename, "wb") as f:
                f.write(img_buf.getvalue())
            return render_template('kilometraje_done.html', email=alias, summary=summary, image=os.path.basename(filename))
    return render_template('kilometraje.html', email=alias, message=message)

@app.route('/resumenes')
def resumenes():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    files = [f for f in os.listdir(BASE_DIR) if f.startswith(f"{safe_alias_from_email(alias)}_summary_") and f.endswith(".json")]
    return render_template('resumenes.html', email=alias, files=sorted(files, reverse=True))

@app.route('/resumen/<filename>')
def view_summary(filename):
    if 'email' not in session:
        return redirect(url_for('index'))
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return "No encontrado", 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return render_template('view_summary.html', email=session['email'], data=data)

@app.route('/imagenes')
def imagenes():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.startswith(f"{safe_alias_from_email(alias)}_") and f.endswith(".png")]
    return render_template('imagenes.html', email=alias, imgs=sorted(imgs, reverse=True))

@app.route('/image/<filename>')
def download_image(filename):
    if 'email' not in session:
        return redirect(url_for('index'))
    path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    return send_file(path, as_attachment=True, download_name=filename)

@app.route('/export')
def exportar():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    csvp = user_csv_path(alias)
    gastos_path = user_gastos_path(alias)
    return render_template('export.html', email=alias, csv_exists=os.path.exists(csvp), gastos_exists=os.path.exists(gastos_path))

@app.route('/download_csv')
def download_csv():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    p = user_csv_path(alias)
    if not os.path.exists(p):
        return "No CSV", 404
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route('/download_gastos')
def download_gastos():
    if 'email' not in session:
        return redirect(url_for('index'))
    p = user_gastos_path(session['email'])
    if not os.path.exists(p):
        return "No gastos", 404
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route('/clear_all')
def clear_all():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    try:
        csvp = user_csv_path(alias)
        gastos = user_gastos_path(alias)
        if os.path.exists(csvp): os.remove(csvp)
        if os.path.exists(gastos): os.remove(gastos)
        for f in os.listdir(BASE_DIR):
            if f.startswith(f"{safe_alias_from_email(alias)}_summary_"):
                os.remove(os.path.join(BASE_DIR, f))
        for f in os.listdir(IMAGES_DIR):
            if f.startswith(safe_alias_from_email(alias) + "_"):
                os.remove(os.path.join(IMAGES_DIR, f))
        ensure_user_csv(alias)
        ensure_gastos_csv(alias)
        return redirect(url_for('index'))
    except Exception as e:
        return f"Error: {e}", 500

# ---------- Presupuesto (Google Sheets) ----------
@app.route('/budget', methods=['GET','POST'])
def budget():
    if 'email' not in session:
        return redirect(url_for('index'))
    email = session['email']
    try:
        df_pres = load_presupuesto_gs()
    except Exception as e:
        app.logger.error("Error loading presupuesto sheet: " + str(e))
        df_pres = pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])

    # alerts 3 days and day of payment
    alerts = []
    hoy = date.today()
    for idx, row in df_pres.iterrows():
        try:
            if str(row.get("alias","")) != email: continue
            if str(row.get("pagado","")).lower() in ("true","1","yes"): continue
            fecha_pago = datetime.strptime(str(row.get("fecha_pago","")), "%Y-%m-%d").date()
            dias_restantes = (fecha_pago - hoy).days
            if dias_restantes == 3:
                alerts.append(("warning", f"En 3 días debes pagar {row.get('categoria')} (S/{row.get('monto')})"))
            elif dias_restantes == 0:
                alerts.append(("danger", f"Hoy debes pagar {row.get('categoria')} (S/{row.get('monto')})"))
        except Exception:
            continue

    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_cat':
            name = request.form.get('cat_name','').strip()
            amount = float(request.form.get('cat_amount','0') or 0)
            fecha_pago = request.form.get('fecha_pago','').strip()
            if not name or amount <= 0 or fecha_pago == "":
                message = {"type":"error","text":"Nombre, monto o fecha inválidos"}
            else:
                new_row = {"alias": email, "categoria": name, "monto": amount, "fecha_pago": fecha_pago, "pagado": "False"}
                df_pres = pd.concat([df_pres, pd.DataFrame([new_row])], ignore_index=True)
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Categoría agregada"}
        elif action == 'delete':
            idx_to_delete = int(request.form.get('idx', -1))
            if idx_to_delete >= 0 and idx_to_delete < len(df_pres):
                df_pres = df_pres.drop(idx_to_delete).reset_index(drop=True)
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Categoría eliminada"}
        elif action == 'mark_paid':
            idx_to_mark = int(request.form.get('idx', -1))
            if idx_to_mark >= 0 and idx_to_mark < len(df_pres):
                df_pres.loc[idx_to_mark, "pagado"] = "True"
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Pago marcado como completado"}

    df_user = df_pres.reset_index().rename(columns={"index":"orig_index"})
    user_rows = df_user[df_user["alias"]==email]
    return render_template('budget.html', email=email, budgets=user_rows.to_dict("records"), message=message, alerts=alerts)

# ---------- Run ----------
if __name__ == "__main__":
    # DEBUG should be False in production
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))# app.py - Trip Counter integrado (Flask) con Google OAuth + Google Sheets (presupuesto)
# Requisitos: flask, requests-oauthlib, pandas, matplotlib, pillow, gspread, google-auth
import os
import sys
import json
import logging
import base64
import re
from datetime import date, datetime
from io import BytesIO
from flask import Flask, redirect, url_for, session, request, render_template, send_file
from requests_oauthlib import OAuth2Session
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger("requests_oauthlib").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

# ---------- Environment / Config ----------
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
DEFAULT_REDIRECT = "https://tripcounter.online/oauth2callback"
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", DEFAULT_REDIRECT).strip()
if REDIRECT_URI.endswith("/"):
    REDIRECT_URI = REDIRECT_URI[:-1]

GSPREAD_SERVICE_ACCOUNT_JSON = os.environ.get("GSPREAD_SERVICE_ACCOUNT_JSON")
GSPREAD_PRESUPUESTO_SHEET_ID = os.environ.get("GSPREAD_PRESUPUESTO_SHEET_ID", "")

# ---------- Flask app ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = FLASK_SECRET_KEY or os.urandom(24)

BASE_DIR = os.path.join(os.getcwd(), "TripCounter_data")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(BASE_DIR, exist_ok=True)

BUTTON_COLOR = "#1034A6"

# OAuth constants
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# ---------- Helpers ----------
def safe_alias_from_email(email: str) -> str:
    base = email.split("@")[0] if "@" in email else email
    return "".join(c for c in base if c.isalnum() or c in ("_", "-")).lower()

def user_csv_path(alias_email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(alias_email)}.csv")

def user_gastos_path(alias_email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(alias_email)}_gastos.csv")

def ensure_user_csv(alias_email: str) -> str:
    path = user_csv_path(alias_email)
    if not os.path.exists(path):
        df = pd.DataFrame(columns=["fecha","tipo","viaje_num","hora_inicio","hora_fin","ganancia_base","aeropuerto","propina","total_viaje"])
        df.to_csv(path, index=False)
    return path

def ensure_gastos_csv(alias_email: str) -> str:
    path = user_gastos_path(alias_email)
    if not os.path.exists(path):
        df = pd.DataFrame(columns=["fecha","concepto","monto"])
        df.to_csv(path, index=False)
    return path

def validate_time_string(t: str) -> bool:
    if not isinstance(t, str) or t.strip() == "":
        return False
    t = t.strip()
    if re.match(r'^[0-2]\d:[0-5]\d$', t):
        hh = int(t.split(":")[0])
        return 0 <= hh <= 23
    return False

def total_of_trips(rows) -> float:
    return sum(float(r.get("total_viaje", 0)) for r in rows)

# ---------- gspread (presupuesto) ----------
def get_gspread_client_from_env():
    if not GSPREAD_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GSPREAD_SERVICE_ACCOUNT_JSON not set in env.")
    try:
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON)
    except Exception:
        # try replace escaped newlines
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON.replace("\\n", "\n"))
    credentials = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.Client(auth=credentials)
    client.session = None
    return client

def load_presupuesto_gs():
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    client = get_gspread_client_from_env()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    df = pd.DataFrame(rows)
    for col in ["alias","categoria","monto","fecha_pago","pagado"]:
        if col not in df.columns:
            df[col] = ""
    return df[["alias","categoria","monto","fecha_pago","pagado"]]

def save_presupuesto_gs(df: pd.DataFrame):
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        return
    client = get_gspread_client_from_env()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    vals = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update(vals)

# ---------- imagenes / gráficos ----------
def generate_balance_image(rows, ingresos, gastos_total, combustible, neto, alias):
    labels = ["Ingresos (S/)", "Gastos (S/)", "Combustible (S/)", "Balance (S/)"]
    values = [round(float(ingresos),2), round(float(gastos_total),2), round(float(combustible),2), round(float(neto),2)]
    fig, ax = plt.subplots(figsize=(8,4.2))
    bars = ax.bar(labels, values, color=["#4da6ff", "#ff7f50", "#ff9f43", "#2ecc71"])
    ax.set_title(f"Balance {date.today().strftime('%Y-%m-%d')} — {alias}")
    top = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, val + top*0.02, f"{val}", ha="center", fontsize=9)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    # overlay logos optionally
    try:
        base_img = Image.open(buf).convert("RGBA")
        overlay = Image.new("RGBA", base_img.size)
        logo_path = os.path.join(IMAGES_DIR, "logo_app.png")
        uber_logo_path = os.path.join(IMAGES_DIR, "logo_uber.png")
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            w = int(base_img.width * 0.15)
            logo = logo.resize((w, int(logo.height*(w/logo.width))))
            overlay.paste(logo, (10,10), logo)
        if os.path.exists(uber_logo_path):
            ulogo = Image.open(uber_logo_path).convert("RGBA")
            w = int(base_img.width * 0.12)
            ulogo = ulogo.resize((w, int(ulogo.height*(w/ulogo.width))))
            overlay.paste(ulogo, (base_img.width - w - 10, 10), ulogo)
        combined = Image.alpha_composite(base_img, overlay)
        out_buf = BytesIO()
        combined.convert("RGB").save(out_buf, format="PNG")
        out_buf.seek(0)
        return out_buf
    except Exception:
        buf.seek(0)
        return buf

# ---------- OAuth endpoints ----------
@app.route('/login')
def login():
    app.logger.info(f"🔁 Iniciando login con redirect_uri: {REDIRECT_URI}")
    if not CLIENT_ID or not CLIENT_SECRET:
        app.logger.error("❌ CLIENT_ID o CLIENT_SECRET no están configurados.")
        return "<h3>Error: Faltan credenciales OAuth.</h3>", 500
    google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    authorization_url, state = google.authorization_url(AUTHORIZE_URL, access_type="offline", prompt="select_account")
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    if 'error' in request.args:
        return f"Google returned error: {request.args.get('error')}", 400
    google = OAuth2Session(CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
    token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.url)
    id_token_jwt = token.get('id_token')
    if id_token_jwt:
        try:
            payload_base64 = id_token_jwt.split('.')[1]
            padding = len(payload_base64) % 4
            payload_base64 += "=" * (4 - padding if padding else 0)
            payload = json.loads(base64.urlsafe_b64decode(payload_base64).decode())
            session['email'] = payload.get('email')
            session['oauth_token'] = token
            app.logger.info(f"✅ Usuario autenticado: {session['email']}")
        except Exception as e:
            app.logger.error("Error decoding id_token: " + str(e))
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ---------- Pages / routes ----------
@app.route('/')
def index():
    email = session.get('email')
    return render_template('home.html', email=email, app_name="Trip Counter", button_color=BUTTON_COLOR)

@app.route('/trips', methods=['GET','POST'])
def trips():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_user_csv(alias)
    message = None
    if request.method == 'POST':
        hi = request.form.get('hi','').strip()
        hf = request.form.get('hf','').strip()
        gan = float(request.form.get('gan','0') or 0)
        aer = True if request.form.get('aer') == 'on' else False
        prop = float(request.form.get('prop','0') or 0)
        errors=[]
        if not validate_time_string(hi): errors.append("Hora inicio inválida")
        if not validate_time_string(hf): errors.append("Hora fin inválida")
        if errors:
            message = {"type":"error","text":"; ".join(errors)}
        else:
            aeropuerto_val = 6.5 if aer else 0.0
            total_v = round(float(gan) + aeropuerto_val + float(prop), 2)
            csvp = user_csv_path(alias)
            df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            viaje_num = len(df) + 1
            new = {
                "fecha": date.today().isoformat(),
                "tipo":"normal",
                "viaje_num": viaje_num,
                "hora_inicio": hi,
                "hora_fin": hf,
                "ganancia_base": float(gan),
                "aeropuerto": aeropuerto_val,
                "propina": float(prop),
                "total_viaje": total_v
            }
            pd.DataFrame([new]).to_csv(csvp, mode='a', header=not os.path.exists(csvp) or os.path.getsize(csvp)==0, index=False)
            message = {"type":"success","text":"Viaje agregado ✅"}
    csvp = user_csv_path(alias)
    df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
    df_today = df[df['fecha']==date.today().isoformat()] if not df.empty else pd.DataFrame()
    return render_template('trips.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/extras', methods=['GET','POST'])
def extras():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_user_csv(alias)
    message=None
    if request.method=='POST':
        hi = request.form.get('hi','').strip()
        hf = request.form.get('hf','').strip()
        gan = float(request.form.get('gan','0') or 0)
        aer = True if request.form.get('aer') == 'on' else False
        prop = float(request.form.get('prop','0') or 0)
        if not validate_time_string(hi) or not validate_time_string(hf):
            message={"type":"error","text":"Hora inválida"}
        else:
            aeropuerto_val = 6.5 if aer else 0.0
            total_v = round(float(gan) + aeropuerto_val + float(prop), 2)
            csvp = user_csv_path(alias)
            df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            viaje_num = len(df) + 1
            new = {
                "fecha": date.today().isoformat(),
                "tipo":"extra",
                "viaje_num": viaje_num,
                "hora_inicio": hi,
                "hora_fin": hf,
                "ganancia_base": float(gan),
                "aeropuerto": aeropuerto_val,
                "propina": float(prop),
                "total_viaje": total_v
            }
            pd.DataFrame([new]).to_csv(csvp, mode='a', header=not os.path.exists(csvp) or os.path.getsize(csvp)==0, index=False)
            message={"type":"success","text":"Viaje extra agregado ✅"}
    csvp = user_csv_path(alias)
    df = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
    df_today = df[(df['fecha']==date.today().isoformat()) & (df['tipo']=='extra')] if not df.empty else pd.DataFrame()
    return render_template('extras.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/gastos', methods=['GET','POST'])
def gastos():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    ensure_gastos_csv(alias)
    message=None
    if request.method=='POST':
        concept = request.form.get('concept','').strip()
        monto = float(request.form.get('monto','0') or 0)
        if not concept or monto <= 0:
            message={"type":"error","text":"Concepto vacío o monto inválido"}
        else:
            gastos_p = user_gastos_path(alias)
            new = {"fecha": date.today().isoformat(), "concepto": concept, "monto": monto}
            pd.DataFrame([new]).to_csv(gastos_p, mode='a', header=not os.path.exists(gastos_p) or os.path.getsize(gastos_p)==0, index=False)
            message={"type":"success","text":"Gasto agregado ✅"}
    gastos_p = user_gastos_path(alias)
    dfg = pd.read_csv(gastos_p) if os.path.exists(gastos_p) and os.path.getsize(gastos_p)>0 else pd.DataFrame()
    df_today = dfg[dfg['fecha']==date.today().isoformat()] if not dfg.empty else pd.DataFrame()
    return render_template('gastos.html', email=alias, table=df_today.to_html(classes='table', index=False), message=message)

@app.route('/kilometraje', methods=['GET','POST'])
def kilometraje():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    message=None
    if request.method=='POST':
        combustible = float(request.form.get('combustible','0') or 0)
        km_final = float(request.form.get('km_final','0') or 0)
        if km_final <= 0:
            message={"type":"error","text":"Debes ingresar el kilometraje final."}
        else:
            csvp = ensure_user_csv(alias)
            df_all = pd.read_csv(csvp) if os.path.exists(csvp) and os.path.getsize(csvp)>0 else pd.DataFrame()
            df_today = df_all[df_all['fecha']==date.today().isoformat()] if not df_all.empty else pd.DataFrame()
            trips_rows = df_today.to_dict("records")
            gastos_path = ensure_gastos_csv(alias)
            gastos_rows = pd.read_csv(gastos_path).to_dict("records") if os.path.exists(gastos_path) and os.path.getsize(gastos_path)>0 else []
            ingresos = total_of_trips(trips_rows)
            gastos_total = sum(float(g.get("monto",0)) for g in gastos_rows)
            neto = round(float(ingresos) - float(gastos_total) - float(combustible), 2)
            summary = {"date": date.today().isoformat(), "total_viajes": len(trips_rows), "ingresos": ingresos, "gastos": gastos_total, "combustible": combustible, "kilometraje": km_final, "total_neto": neto}
            sum_path = os.path.join(BASE_DIR, f"{safe_alias_from_email(alias)}_summary_{date.today().isoformat()}.json")
            with open(sum_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            img_buf = generate_balance_image(trips_rows, ingresos, gastos_total, combustible, neto, alias)
            filename = os.path.join(IMAGES_DIR, f"{safe_alias_from_email(alias)}_{date.today().isoformat()}.png")
            with open(filename, "wb") as f:
                f.write(img_buf.getvalue())
            return render_template('kilometraje_done.html', email=alias, summary=summary, image=os.path.basename(filename))
    return render_template('kilometraje.html', email=alias, message=message)

@app.route('/resumenes')
def resumenes():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    files = [f for f in os.listdir(BASE_DIR) if f.startswith(f"{safe_alias_from_email(alias)}_summary_") and f.endswith(".json")]
    return render_template('resumenes.html', email=alias, files=sorted(files, reverse=True))

@app.route('/resumen/<filename>')
def view_summary(filename):
    if 'email' not in session:
        return redirect(url_for('index'))
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return "No encontrado", 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return render_template('view_summary.html', email=session['email'], data=data)

@app.route('/imagenes')
def imagenes():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.startswith(f"{safe_alias_from_email(alias)}_") and f.endswith(".png")]
    return render_template('imagenes.html', email=alias, imgs=sorted(imgs, reverse=True))

@app.route('/image/<filename>')
def download_image(filename):
    if 'email' not in session:
        return redirect(url_for('index'))
    path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    return send_file(path, as_attachment=True, download_name=filename)

@app.route('/export')
def exportar():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    csvp = user_csv_path(alias)
    gastos_path = user_gastos_path(alias)
    return render_template('export.html', email=alias, csv_exists=os.path.exists(csvp), gastos_exists=os.path.exists(gastos_path))

@app.route('/download_csv')
def download_csv():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    p = user_csv_path(alias)
    if not os.path.exists(p):
        return "No CSV", 404
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route('/download_gastos')
def download_gastos():
    if 'email' not in session:
        return redirect(url_for('index'))
    p = user_gastos_path(session['email'])
    if not os.path.exists(p):
        return "No gastos", 404
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))

@app.route('/clear_all')
def clear_all():
    if 'email' not in session:
        return redirect(url_for('index'))
    alias = session['email']
    try:
        csvp = user_csv_path(alias)
        gastos = user_gastos_path(alias)
        if os.path.exists(csvp): os.remove(csvp)
        if os.path.exists(gastos): os.remove(gastos)
        for f in os.listdir(BASE_DIR):
            if f.startswith(f"{safe_alias_from_email(alias)}_summary_"):
                os.remove(os.path.join(BASE_DIR, f))
        for f in os.listdir(IMAGES_DIR):
            if f.startswith(safe_alias_from_email(alias) + "_"):
                os.remove(os.path.join(IMAGES_DIR, f))
        ensure_user_csv(alias)
        ensure_gastos_csv(alias)
        return redirect(url_for('index'))
    except Exception as e:
        return f"Error: {e}", 500

# ---------- Presupuesto (Google Sheets) ----------
@app.route('/budget', methods=['GET','POST'])
def budget():
    if 'email' not in session:
        return redirect(url_for('index'))
    email = session['email']
    try:
        df_pres = load_presupuesto_gs()
    except Exception as e:
        app.logger.error("Error loading presupuesto sheet: " + str(e))
        df_pres = pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])

    # alerts 3 days and day of payment
    alerts = []
    hoy = date.today()
    for idx, row in df_pres.iterrows():
        try:
            if str(row.get("alias","")) != email: continue
            if str(row.get("pagado","")).lower() in ("true","1","yes"): continue
            fecha_pago = datetime.strptime(str(row.get("fecha_pago","")), "%Y-%m-%d").date()
            dias_restantes = (fecha_pago - hoy).days
            if dias_restantes == 3:
                alerts.append(("warning", f"En 3 días debes pagar {row.get('categoria')} (S/{row.get('monto')})"))
            elif dias_restantes == 0:
                alerts.append(("danger", f"Hoy debes pagar {row.get('categoria')} (S/{row.get('monto')})"))
        except Exception:
            continue

    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_cat':
            name = request.form.get('cat_name','').strip()
            amount = float(request.form.get('cat_amount','0') or 0)
            fecha_pago = request.form.get('fecha_pago','').strip()
            if not name or amount <= 0 or fecha_pago == "":
                message = {"type":"error","text":"Nombre, monto o fecha inválidos"}
            else:
                new_row = {"alias": email, "categoria": name, "monto": amount, "fecha_pago": fecha_pago, "pagado": "False"}
                df_pres = pd.concat([df_pres, pd.DataFrame([new_row])], ignore_index=True)
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Categoría agregada"}
        elif action == 'delete':
            idx_to_delete = int(request.form.get('idx', -1))
            if idx_to_delete >= 0 and idx_to_delete < len(df_pres):
                df_pres = df_pres.drop(idx_to_delete).reset_index(drop=True)
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Categoría eliminada"}
        elif action == 'mark_paid':
            idx_to_mark = int(request.form.get('idx', -1))
            if idx_to_mark >= 0 and idx_to_mark < len(df_pres):
                df_pres.loc[idx_to_mark, "pagado"] = "True"
                save_presupuesto_gs(df_pres)
                message = {"type":"success","text":"Pago marcado como completado"}

    df_user = df_pres.reset_index().rename(columns={"index":"orig_index"})
    user_rows = df_user[df_user["alias"]==email]
    return render_template('budget.html', email=email, budgets=user_rows.to_dict("records"), message=message, alerts=alerts)

# ---------- Run ----------
if __name__ == "__main__":
    # DEBUG should be False in production
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))