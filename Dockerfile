# 1. Imagen base de Python
FROM python:3.10-slim

# 2. Instalar dependencias del sistema para Playwright
# Estas son las librerías de Linux que Chromium necesita para correr
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    # Limpiar el cache de apt
    && rm -rf /var/lib/apt/lists/*

# 3. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Instalar el navegador Chromium y sus dependencias de OS
RUN playwright install chromium --with-deps

# 6. Copiar todo el código de tu backend (app.py, carpeta /scrapers)
COPY . .

# 7. Comando para ejecutar la aplicación
# Railway asignará un $PORT automáticamente.
# Uvicorn correrá el objeto 'app' (FastAPI) desde el archivo 'app.py'
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port $PORT"]