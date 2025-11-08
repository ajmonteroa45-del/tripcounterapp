# app.py: Aplicación Flask para Render con Autenticación Google OAuth

from flask import Flask, redirect, url_for, session, request, render_template_string
from requests_oauthlib import OAuth2Session
from datetime import timedelta
import os, logging, jwt, json

# ==============================
# 1. CONFIGURACIÓN DE LOGGING
# ==============================
logging.basicConfig(level=logging.INFO)

# ==============================
# 2. VARIABLES DE ENTORNO
# ==============================
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "https://tripcounter.online/oauth2callback")

# URLs estándar de Google OAuth
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

# ==============================
# 3. CONFIGURACIÓN DE FLASK
# ==============================
app = Flask(__name__)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Manejo robusto de la clave secreta
if not FLASK_SECRET_KEY:
    FLASK_SECRET_KEY = os.urandom(24)
    app.logger.warning("⚠️ Variable de entorno FLASK_SECRET_KEY no encontrada. Se usará una clave temporal.")
else:
    app.logger.info("✅ FLASK_SECRET_KEY cargada correctamente desde el entorno.")

app.secret_key = FLASK_SECRET_KEY

# ==============================
# 4. RUTAS PRINCIPALES
# ==============================
@app.route('/')
def home():
    """Ruta principal que muestra la interfaz de la aplicación o el botón de login."""
    if 'email' in session:
        user_email = session['email']
        return render_template_string("""
            <h1>Bienvenido a Trip Counter, {{ email }}</h1>
            <p>Aquí irá toda la lógica de tus pestañas (Uber/Didi, Gastos, etc.).</p>
            <a href="/logout"><button>Cerrar Sesión</button></a>
        """, email=user_email)
    else:
        return render_template_string("""
            <h1>Inicia Sesión para Acceder a Trip Counter</h1>
            <a href="/login">
                <button style="padding: 10px; background-color: #1034A6; color: white; border-radius: 5px;">
                    Iniciar Sesión con Google
                </button>
            </a>
            <p>Lee nuestra <a href="https://policy.tripcounter.online" target="_blank">Política de Privacidad</a>.</p>
        """)

# ==============================
# 5. FLUJO DE OAUTH GOOGLE
# ==============================
@app.route('/login')
def login():
    """Inicia el flujo de autenticación de Google OAuth."""
    app.logger.info(f"🔁 Iniciando login con redirect_uri: {REDIRECT_URI}")

    try:
        google = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
        authorization_url, state = google.authorization_url(
            AUTHORIZE_URL,
            access_type="offline",
            prompt="select_account"
        )
        session['oauth_state'] = state
        app.logger.info(f"🌐 Redirigiendo a URL de autorización: {authorization_url}")
        return redirect(authorization_url)
    except Exception as e:
        app.logger.error(f"❌ Error iniciando sesión: {str(e)}")
        return f"<h3>Error iniciando sesión: {e}</h3>", 500


@app.route('/oauth2callback')
def oauth2callback():
    """Maneja la respuesta de Google y obtiene el token de acceso."""
    app.logger.info("🔁 Recibiendo callback de Google OAuth")

    if 'error' in request.args:
        error = request.args.get('error')
        app.logger.error(f"⚠️ Error devuelto por Google: {error}")
        return f"<h3>Error devuelto por Google: {error}</h3>", 400

    try:
        google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=session.get('oauth_state'))
        token = google.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            authorization_response=request.url
        )
        session['oauth_token'] = token

        # Obtener información del usuario
        user_info = google.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
        session['email'] = user_info.get('email')

        app.logger.info(f"✅ Usuario autenticado: {session['email']}")
        return redirect(url_for('home'))

    except Exception as e:
        app.logger.error(f"❌ Error en el callback OAuth: {str(e)}")
        return f"<h3>Error procesando callback: {e}</h3>", 500

# ==============================
# 6. CERRAR SESIÓN
# ==============================
@app.route('/logout')
def logout():
    session.clear()
    app.logger.info("👋 Sesión cerrada correctamente.")
    return redirect(url_for('home'))

# ==============================
# 7. PUNTO DE ENTRADA
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))