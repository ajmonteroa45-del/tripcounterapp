# app.py: Aplicación Flask para Render con Autenticación Google OAuth

from flask import Flask, redirect, url_for, session, request, render_template_string
from requests_oauthlib import OAuth2Session
from datetime import timedelta
import os, base64, json, logging, jwt

# --- 1. CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- 2. CONFIGURACIÓN DE VARIABLES DE ENTORNO ---

CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "https://www.tripcounter.online/oauth2callback")

# --- 3. URLs ESTÁNDAR DE GOOGLE ---
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# --- 4. CONFIGURACIÓN DE FLASK ---
app = Flask(__name__)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Manejo robusto de la clave secreta
if not FLASK_SECRET_KEY:
    FLASK_SECRET_KEY = os.urandom(24)
    app.logger.warning("⚠️ Variable de entorno FLASK_SECRET_KEY no encontrada. Se usará una clave temporal.")
else:
    app.logger.info("✅ FLASK_SECRET_KEY cargada correctamente desde el entorno.")

app.secret_key = FLASK_SECRET_KEY


# --- 5. RUTAS DE INTERFAZ ---

@app.route('/')
def home():
    """Ruta principal que muestra la interfaz de la aplicación o el botón de login."""
    if 'email' in session:
        user_email = session['email']
        return render_template_string("""
            <h1>Bienvenido a Trip Counter, {{ email }}</h1>
            <p>Aquí irá toda la lógica de tus pestañas (Uber/Didi, Gastos, etc.), reescrita sin Streamlit.</p>
            <a href="/logout"><button>Cerrar Sesión</button></a>
        """, email=user_email)
    else:
        return render_template_string("""
            <h1>Inicia Sesión para Acceder a Trip Counter</h1>
            <a href="/login"><button style="padding: 10px; background-color: #1034A6; color: white; border-radius: 5px;">Iniciar Sesión con Google</button></a>
            <p>Lee nuestra <a href="https://policy.tripcounter.online" target="_blank">Política de Privacidad</a>.</p>
        """)


# --- 6. LÓGICA DE OAUTH ---

@app.route('/login')
def login():
    """Inicia el flujo de autenticación de Google OAuth."""
    google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    authorization_url, state = google.authorization_url(
        AUTHORIZE_URL, 
        access_type="offline", 
        prompt="select_account"
    )
    session['oauth_state'] = state
    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    """Maneja la respuesta de Google y obtiene el token de acceso."""