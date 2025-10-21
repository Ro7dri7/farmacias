# 1. USAR LA IMAGEN OFICIAL DE PLAYWRIGHT
# Esta imagen ya tiene Python 3.10+, Playwright y los navegadores (Chromium, etc.)
# Usamos "jammy" que es la versión basada en Ubuntu 22.04
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# 2. Establecer el directorio de trabajo
WORKDIR /app

# 3. Copiar el archivo de requisitos
COPY requirements.txt .

# 4. Instalar TUS OTRAS dependencias (FastAPI, uvicorn, etc.)
# Playwright ya viene instalado, pero pip es lo suficientemente inteligente
# para saltárselo si ya está en la versión correcta.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar TODO el resto de tu código (app.py, carpeta scrapers/, etc.)
COPY . .

# 6. Exponer el puerto 8000 (el mismo que usa FastAPI)
EXPOSE 8000

# 7. El comando para iniciar tu servidor FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]