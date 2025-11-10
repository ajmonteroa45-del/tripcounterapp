# app.py - Trip Counter (Flask) - versión limpia (sin Streamlit)
import os
import json
import base64
import logging
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from flask import Flask, redirect, url_for, session, request, render_template, send_file, flash
from requests_oauthlib import OAuth2Session
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tripcounter")

# ---- Config / env ----
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24).hex()
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "").rstrip("/")  # e.g. https://tripcounter.online/oauth2callback

GSPREAD_SERVICE_ACCOUNT_JSON = os.environ.get("GSPREAD_SERVICE_ACCOUNT_JSON")  # JSON string
GSPREAD_PRESUPUESTO_SHEET_ID = os.environ.get("GSPREAD_PRESUPUESTO_SHEET_ID", "")

# Fallback default redirect if not set (useful for local dev)
if not REDIRECT_URI:
    # local dev default (change when deploying)
    REDIRECT_URI = "http://localhost:5000/oauth2callback"

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# ---- Flask app ----
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = FLASK_SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# ---- Paths ----
BASE_DIR = os.path.join(os.getcwd(), "data")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(BASE_DIR, exist_ok=True)

# ---- Helpers ----
def get_gspread_client():
    if not GSPREAD_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GSPREAD_SERVICE_ACCOUNT_JSON not set")
    try:
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON)
    except Exception:
        # maybe newlines were escaped
        creds_dict = json.loads(GSPREAD_SERVICE_ACCOUNT_JSON.replace("\\n", "\n"))
    credentials = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.Client(auth=credentials)
    client.session = None
    return client

def load_presupuesto_sheet():
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        # return empty DataFrame with expected columns
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    client = get_gspread_client()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=["alias","categoria","monto","fecha_pago","pagado"])
    df = pd.DataFrame(rows)
    # ensure columns exist
    for c in ["alias","categoria","monto","fecha_pago","pagado"]:
        if c not in df.columns:
            df[c] = ""
    return df[["alias","categoria","monto","fecha_pago","pagado"]]

def save_presupuesto_sheet(df: pd.DataFrame):
    if not GSPREAD_PRESUPUESTO_SHEET_ID:
        return
    client = get_gspread_client()
    ws = client.open_by_key(GSPREAD_PRESUPUESTO_SHEET_ID).sheet1
    rows = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update(rows)

def safe_alias_from_email(email: str) -> str:
    base = email.split("@")[0] if "@" in email else email
    return "".join(c for c in base if c.isalnum() or c in ("_","-")).lower()

def user_csv_path(email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(email)}.csv")

def gastos_csv_path(email: str) -> str:
    return os.path.join(BASE_DIR, f"{safe_alias_from_email(email)}_gastos.csv")

def ensure_csvs_for(email: str):
    p = user_csv_path(email)
    if not os.path.exists(p):
        pd.DataFrame(columns=["fecha","tipo","viaje_num","hora_inicio","hora_fin","ganancia_base","aeropuerto","propina","total_viaje"]).to_csv(p, index=False)
    gp = gastos_csv_path(email)
    if not os.path.exists(gp):
        pd.DataFrame(columns=["fecha","concepto","monto"]).to_csv(gp, index=False)

def validate_time_string(t: str) -> bool:
    if not isinstance(t, str) or t.strip()=="":
        return False
    if re.match(r'^[0-2]\d:[0-5]\d$', t.strip()):
        hh = int(t.split(":")[0])
        return 0 <= hh <= 23
    return False

def generate_balance_image(rows, ingresos, gastos_total, combustible, neto, alias):
    labels = ["Ingresos (S/)", "Gastos (S/)", "Combustible (S/)", "Balance (S/)"]
    values = [round(float(ingresos),2), round(float(gastos_total),2), round(float(combustible),2), round(float(neto),2)]
    fig, ax = plt.subplots(figsize=(8,4.2))
    bars = ax.bar(labels, values)
    ax.set_title(f"Balance {date.today().strftime('%Y-%m-%d')} — {alias}")
    top = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, val + top*0.02, f"{val}", ha="center", fontsize=9)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    # overlay logo if exists
    try:
        base_img = Image.open(buf).convert("RGBA")
        overlay = Image.new("RGBA", base_img.size)
        logo_path = os.path.join(IMAGES_DIR, "logo_app.png")
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            w = int(base_img.width * 0.12)
            logo = logo.resize((w, int(logo.height*(w/logo.width))))
            overlay.paste(logo, (10,10), logo)
        combined = Image.alpha_composite(base_img, overlay)
        out = BytesIO()
        combined.convert("RGB").save(out, format="PNG")
        out.seek(0)
        return out
    except Exception:
        buf.seek(0)
        return buf

# ---- Routes ----
@app.route("/")
def index():
    email = session.get("email")
    return render_template("home.html", email=email)

@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Error: CLIENT_ID or CLIENT_SECRET not configured in environment.", 500
    google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    auth_url, state = google.authorization_url(AUTHORIZE_URL, access_type="offline", prompt="select_account")
    session['oauth_state'] = state
    logger.info("Redirecting user to Google OAuth")
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    if 'error' in request.args:
        return f"Error from provider: {request.args.get('error')}", 400
    google = OAuth2Session(CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
    try:
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.url)
    except Exception as e:
        logger.error("fetch_token error: %s", e)
        return f"Error fetching token: {e}", 500
    id_token = token.get("id_token")
    if id_token:
        try:
            payload_b64 = id_token.split(".")[1]
            padding = len(payload_b64) % 4
            payload_b64 += "=" * (4 - padding if padding else 0)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
            session['email'] = payload.get('email')
            session['oauth_token'] = token
            ensure_csvs_for(session['email'])
            logger.info("User logged in: %s", session['email'])
            return redirect(url_for("index"))
        except Exception as e:
            logger.error("ID token decode error: %s", e)
            # fallback: try userinfo endpoint
    # fallback to userinfo
    try:
        resp = google.get("https://www.googleapis.com/oauth2/v2/userinfo").json()
        session['email'] = resp.get("email")
        ensure_csvs_for(session['email'])
        return redirect(url_for("index"))
    except Exception as e:
        logger.error("userinfo fetch error: %s", e)
        return "Authentication failed", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---- Budget routes (Google Sheets) ----
@app.route("/budget", methods=["GET", "POST"])
def budget():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    df = load_presupuesto_sheet()
    user_df = df[df["alias"] == email].reset_index()
    message = ""
    if request.method == "POST":
        # add new category
        categoria = request.form.get("categoria", "").strip()
        monto = request.form.get("monto", "").strip()
        fecha_pago = request.form.get("fecha_pago", "").strip()
        if categoria and monto and fecha_pago:
            new = {"alias": email, "categoria": categoria, "monto": monto, "fecha_pago": fecha_pago, "pagado": "False"}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            save_presupuesto_sheet(df)
            message = "Categoría agregada"
            user_df = df[df["alias"] == email].reset_index()
    return render_template("budget.html", email=email, df=user_df.to_dict("records"), message=message)

@app.route("/budget/mark_paid/<int:index>")
def budget_mark_paid(index):
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    df = load_presupuesto_sheet()
    if index in df.index:
        df.loc[index, "pagado"] = "True"
        save_presupuesto_sheet(df)
    return redirect(url_for("budget"))

# ---- Trips / gastos / resumen flow ----
@app.route("/trips", methods=["GET","POST"])
def trips():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    ensure_csvs_for(email)
    msg = ""
    if request.method == "POST":
        hi = request.form.get("hi","").strip()
        hf = request.form.get("hf","").strip()
        gan = float(request.form.get("gan","0") or 0)
        aer = request.form.get("aer") == "on"
        prop = float(request.form.get("prop","0") or 0)
        if not validate_time_string(hi) or not validate_time_string(hf):
            msg = "Formato de hora inválido (HH:MM)"
        else:
            aeropuerto_val = 6.5 if aer else 0.0
            total_v = round(gan + aeropuerto_val + prop, 2)
            p = user_csv_path(email)
            df = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
            viaje_num = len(df) + 1
            new = {"fecha": date.today().isoformat(), "tipo":"normal", "viaje_num":viaje_num, "hora_inicio":hi, "hora_fin":hf,
                   "ganancia_base":gan, "aeropuerto":aeropuerto_val, "propina":prop, "total_viaje":total_v}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            df.to_csv(p, index=False)
            msg = "Viaje registrado"
    return render_template("trips.html", email=email, message=msg)

@app.route("/gastos", methods=["GET","POST"])
def gastos():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    gp = gastos_csv_path(email)
    if request.method == "POST":
        concepto = request.form.get("concepto","").strip()
        monto = float(request.form.get("monto","0") or 0)
        df = pd.read_csv(gp) if os.path.exists(gp) else pd.DataFrame()
        new = {"fecha": date.today().isoformat(), "concepto":concepto, "monto":monto}
        df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
        df.to_csv(gp, index=False)
        return redirect(url_for("gastos"))
    df = pd.read_csv(gp) if os.path.exists(gp) else pd.DataFrame()
    return render_template("gastos.html", email=email, gastos=df.to_dict("records"))

@app.route("/kilometraje", methods=["GET","POST"])
def kilometraje():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    if request.method == "POST":
        combustible = float(request.form.get("combustible","0") or 0)
        km = float(request.form.get("km","0") or 0)
        # generate summary for today's trips
        p = user_csv_path(email)
        df = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
        df_today = df[df["fecha"] == date.today().isoformat()]
        trips_rows = df_today.to_dict("records")
        gp = gastos_csv_path(email)
        gastos_rows = pd.read_csv(gp).to_dict("records") if os.path.exists(gp) else []
        ingresos = sum(r.get("total_viaje",0) for r in trips_rows)
        gastos_total = sum(g.get("monto",0) for g in gastos_rows)
        neto = round(float(ingresos) - float(gastos_total) - float(combustible), 2)
        summary = {"date": date.today().isoformat(), "total_viajes": len(trips_rows), "ingresos": ingresos, "gastos": gastos_total, "combustible":combustible, "kilometraje":km, "total_neto":neto}
        # save summary
        sum_path = os.path.join(BASE_DIR, f"{safe_alias_from_email(email)}_summary_{date.today().isoformat()}.json")
        with open(sum_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        # image
        imgbuf = generate_balance_image(trips_rows, ingresos, gastos_total, combustible, neto, safe_alias_from_email(email))
        imgname = os.path.join(IMAGES_DIR, f"{safe_alias_from_email(email)}_{date.today().isoformat()}.png")
        with open(imgname, "wb") as f:
            f.write(imgbuf.getvalue())
        return render_template("kilometraje_done.html", email=email, summary=summary, image_url=url_for("static", filename=f"../data/images/{os.path.basename(imgname)}"))
    return render_template("kilometraje.html", email=email)

@app.route("/resumenes")
def resumenes():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    files = [f for f in os.listdir(BASE_DIR) if f.startswith(safe_alias_from_email(email) + "_summary_") and f.endswith(".json")]
    files_sorted = sorted(files, reverse=True)
    summaries = []
    for f in files_sorted:
        with open(os.path.join(BASE_DIR, f), "r", encoding="utf-8") as fh:
            summaries.append(json.load(fh))
    return render_template("resumenes.html", email=email, summaries=summaries)

@app.route("/imagenes")
def imagenes():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.startswith(safe_alias_from_email(email))]
    imgs_sorted = sorted(imgs, reverse=True)
    return render_template("imagenes.html", email=email, images=imgs_sorted)

@app.route("/static_image/<filename>")
def static_image(filename):
    # serve saved generated images under data/images
    return send_file(os.path.join(IMAGES_DIR, filename), mimetype="image/png")

@app.route("/exportar")
def exportar():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))
    csvp = user_csv_path(email)
    gp = gastos_csv_path(email)
    files = {}
    if os.path.exists(csvp):
        files['viajes'] = csvp
    if os.path.exists(gp):
        files['gastos'] = gp
    return render_template("exportar.html", email=email, files=files)

# ---- Health ----
@app.route("/healthz")
def healthz():
    return "ok", 200
# Ruta para la página de viajes extra (arregla el error de url_for('extras'))
@app.route("/extras")
def extras():
    return render_template("extras.html")

# ---- Run ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # In production use gunicorn; this block is for local dev
    app.run(host="0.0.0.0", port=port)