import asyncio
import sys

# -----------------------------------------------------------------
# SOLUCIÓN para NotImplementedError en Windows
# -----------------------------------------------------------------
# Esto fuerza a asyncio a usar un "event loop" compatible 
# con Playwright en Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# -----------------------------------------------------------------


# --- El resto de tu código ---
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# 'sys' ya fue importado arriba

# -----------------------------------------------------------------
# IMPORTANTE: Importa tu función desde la carpeta 'scrapers'
# -----------------------------------------------------------------
try:
    from scrapers.farmacia_scrapers import comparar_precios_playwright
except ImportError:
    print("Error: No se pudo importar 'comparar_precios_playwright'.")
    print("Asegúrate de tener la carpeta 'scrapers' con el archivo 'farmacia_scrapers.py' y un '__init__.py' vacío.")
    sys.exit(1)


app = FastAPI(
    title="API de Scraper de Farmacias",
    description="Una API para comparar precios de farmacias en Perú.",
    version="1.0.0"
)

# --- Configuración de CORS ---
# Permite que tu frontend (en otro dominio) se comunique con este backend.
origins = [
    "*",  # Permite todo para desarrollo.
    # En producción, deberías poner aquí la URL de tu frontend:
    # "https://mi-frontend-123.up.railway.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite GET, POST, etc.
    allow_headers=["*"], # Permite cualquier header
)


# --- Endpoints de la API ---

@app.get("/")
def read_root():
    """Endpoint raíz para verificar que la API está viva."""
    return {"status": "API del scraper de farmacias funcionando."}


@app.get("/api/buscar")
async def buscar_productos(keyword: str):
    """
    Endpoint principal para buscar productos.
    Se usa así: /api/buscar?keyword=panadol
    """
    if not keyword or len(keyword.strip()) < 2:
        raise HTTPException(
            status_code=400, 
            detail="El parámetro 'keyword' es requerido y debe tener al menos 2 caracteres."
        )
    
    print(f"--- Iniciando búsqueda para: {keyword} ---")
    
    try:
        # Limitamos a 10 items por farmacia para que la respuesta
        # sea rápida y no cause un 'timeout' en el servidor.
        resultados = await comparar_precios_playwright(keyword, max_items=10)
        
        print(f"--- Búsqueda completada. {len(resultados)} productos encontrados. ---")
        
        if not resultados:
            return {"data": [], "message": "No se encontraron productos."}
            
        return {"data": resultados}
    
    except Exception as e:
        print(f"--- ERROR GRAVE DURANTE EL SCRAPING: {e} ---")
        # Informa al cliente que algo salió mal en el servidor
        raise HTTPException(
            status_code=500, 
            detail=f"Ocurrió un error interno en el servidor: {e}"
        )

# Esto solo se usa si ejecutas `python app.py` localmente
if __name__ == "__main__":
    print("Iniciando servidor localmente en http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)