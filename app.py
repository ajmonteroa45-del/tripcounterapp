# app.py: Aplicación Flask para Render con Autenticación Google OAuth
from flask import Flask, redirect, url_for, session, request, render_template_string
from requests_oauthlib import OAuth2Session
from datetime import timedelta
import os, base64, json
import logging
import jwt  # Necesario para decodificación de JWT (aunque no se use para la validación de firma final)

# Configuración del logging
logging.basicConfig(level=logging.INFO)

# --- 1. CONFIGURACIÓN DE LA APLICACIÓN Y SECRETOS ---

# NOTA: Estas variables se leen desde las variables de entorno de Render
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")

# Esta variable se añade para flexibilidad y se lee desde Render
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "https://www.tripcounter.online/oauth2callback")

# URLs Estándar de Google
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = ["openid", "email", "profile"]

app = Flask(__name__)

# Configuración de seguridad para la sesión de Flask
# Puedes descomentar el print para verificar si Render ve la variable:
# print(">>> FLASK_SECRET_KEY =", os.environ.get("FLASK_SECRET_KEY"))

if not FLASK_SECRET_KEY:
    raise RuntimeError("La variable de entorno FLASK_SECRET_KEY no está configurada.")

app.secret_key = FLASK_SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# --- 2. RUTAS DE INTERFAZ ---

@app.route('/')
def home():
    """Ruta principal que muestra la interfaz de la aplicación o el botón de login."""
    if 'email' in session:
        user_email = session['email']
        # --- CÓDIGO DE LA APLICACIÓN PRINCIPAL (Contenido Autenticado) ---
        return render_template_string("""
            <h1>Bienvenido a Trip Counter, {{ email }}</h1>
            <p>Aquí irá toda la lógica de tus pestañas (Uber/Didi, Gastos, etc.), reescrita sin Streamlit.</p>
            <a href="/logout"><button>Cerrar Sesión</button></a>
        """, email=user_email)
    else:
        # Página de inicio de sesión
        return render_template_string("""
            <h1>Inicia Sesión para Acceder a Trip Counter</h1>
            <a href="/login"><button style="padding: 10px; background-color: #1034A6; color: white; border-radius: 5px;">Iniciar Sesión con Google</button></a>
            <p>Lee nuestra <a href="https://policy.tripcounter.online" target="_blank">Política de Privacidad</a>.</p>
        """)

# --- 3. LÓGICA DE OAUTH ---

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
    google = OAuth2Session(CLIENT_ID, state=session.get('oauth_state'), redirect_uri=REDIRECT_URI)
    
    try:
        token = google.fetch_token(
            TOKEN_URL, 
            client_secret=CLIENT_SECRET, 
            authorization_response=request.url
        )
        
        id_token_jwt = token.get('id_token')
        if id_token_jwt:
            # Decodificación simple del payload (para fines de prueba)
            payload_base64 = id_token_jwt.split('.')[1]
            # Añade padding si es necesario
            padding = len(payload_base64) % 4
            payload_base64 += "=" * (4 - padding if padding else 0)
            
            payload = json.loads(base64.urlsafe_b64decode(payload_base64).decode())
            
            session['email'] = payload.get('email')
            session['token'] = token
            
            return redirect(url_for('home'))
        
    except Exception as e:
        app.logger.error(f"Error en OAuth callback: {e}")
        return f"Fallo de autenticación (Error interno). Inténtalo de nuevo. Detalle: {e}", 500

@app.route('/logout')
def logout():
    """Cierra la sesión del usuario."""
    session.clear()
    return redirect(url_for('home'))


# --- 4. EJECUCIÓN LOCAL (Render usa Gunicorn) ---
if __name__ == '__main__':
    # Solo se usa en desarrollo local, Render usará gunicorn app:app
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)