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
    return redirect(url_for('home'))


if __name__ == '__main__':
    # Usamos Gunicorn para producción en Render, pero Flask para desarrollo local
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)