# Usa una imagen ligera de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Indicar el puerto que Render usará
ENV PORT=10000

# Exponer el puerto
EXPOSE 10000

# Comando para ejecutar Flask (Render usa la variable $PORT automáticamente)
CMD ["gunicorn", "app:app", "--log-level", "debug", "--capture-output", "--enable-stdio-inheritance"]
