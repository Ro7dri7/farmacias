import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import time

# --- ¡LA CONEXIÓN CLAVE! ---
# Importamos tu función principal desde el archivo en la carpeta /scrapers
from scrapers.farmacia_scrapers import comparar_precios_playwright
# --------------------------------

app = FastAPI(
    title="API de Scraper de Farmacias",
    description="Una API que compara precios de productos en farmacias peruanas usando Playwright.",
    version="1.0.0"
)

# --- CONFIGURACIÓN DE CORS ---
# Esto es VITAL para que tu frontend (React, Vue, etc.)
# pueda conectarse a esta API.
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173", # Puerto común de Vite/React
    "*"  # Permite todo (fácil para probar, pero más restrictivo en producción)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST)
    allow_headers=["*"],  # Permite todos los headers
)
# -----------------------------


@app.get("/")
def read_root():
    """Ruta raíz para verificar que el servidor está funcionando."""
    return {"status": "ok", "message": "Bienvenido al Scraper API de Farmacias"}


# --- ESTE ES TU ENDPOINT PRINCIPAL ---
@app.get("/buscar_productos")
async def buscar_productos(keyword: str):
    """
    Recibe un 'keyword' (término de búsqueda) y devuelve una lista 
    de productos encontrados en las diferentes farmacias.
    """
    
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="El parámetro 'keyword' es requerido y no puede estar vacío.")
        
    print(f"--- 🚀 INICIANDO BÚSQUEDA PARA: {keyword} ---")
    start_time = time.time()
    
    try:
        # Llamamos a tu función de scraping asíncrona
        # Esta es la función que lanza los 5 scrapers en paralelo
        resultados = await comparar_precios_playwright(keyword)
        
        end_time = time.time()
        total_time = end_time - start_time
        print(f"--- ✅ BÚSQUEDA FINALIZADA. {len(resultados)} productos encontrados en {total_time:.2f} segundos. ---")
        
        if not resultados:
            # Si la lista está vacía, igual damos una respuesta exitosa
            return {"data": [], "message": "No se encontraron productos para este término."}
        
        return {"data": resultados, "message": f"Se encontraron {len(resultados)} productos."}

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"--- ❌ ERROR GRAVE DURANTE EL SCRAPING: {e} (después de {total_time:.2f} segundos) ---")
        # Informa al cliente que algo salió mal en el servidor
        raise HTTPException(
            status_code=500,
            detail=f"Ocurrió un error interno en el servidor: {str(e)}"
        )
# --------------------------------------


# Esto solo se usa si ejecutas `python app.py` localmente
# Railway usará el comando del Dockerfile (CMD)
if __name__ == "__main__":
    print("Iniciando servidor localmente en http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)