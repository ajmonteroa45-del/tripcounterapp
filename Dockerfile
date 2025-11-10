# Dockerfile - entorno fijo en Python 3.11
FROM python:3.11-slim

# Librerías del sistema necesarias para Pillow y matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PORT=10000
EXPOSE 10000

# Si tu app principal es Streamlit:
CMD ["streamlit", "run", "app.py", "--server.port=10000", "--server.address=0.0.0.0"]

# Si usas Flask con gunicorn, cambia la línea anterior por:
# CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "2"]
