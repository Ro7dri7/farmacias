import asyncio
import re
from urllib.parse import urljoin, quote_plus
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# NOTA: Pandas, ipywidgets, etc., no son necesarios aquí
# solo las librerías para el scraping en sí.

# User-Agent estándar para evitar bloqueos
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def limpiar_precio(texto: str) -> str:
    """Extrae y formatea el primer precio 'S/ XX.XX' encontrado."""
    if not texto:
        return "No disponible"

    # Busca el patrón S/ seguido de números, comas y puntos
    match = re.search(r'S/\s*([\d,\.]+)', texto)
    if match:
        precio_num = match.group(1).replace(',', '') # Quita comas de miles
        try:
            # Formatea a dos decimales
            return f"S/ {float(precio_num):.2f}"
        except ValueError:
            return f"S/ {precio_num}" # Devuelve lo que encontró si no puede castear

    return "No disponible"

async def crear_contexto_navegador(playwright_instance):
    """Lanza el navegador y crea un contexto con configuración anti-bot."""
    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process"
        ]
    )
    context = await browser.new_context(
        user_agent=USER_AGENT,
        java_script_enabled=True,
        bypass_csp=True
    )
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return browser, context

# =============================================
# SCRAPER INKAFARMA Y MIFARMA
# =============================================
async def scrape_farmacia_playwright(url: str, farmacia: str, max_items: int = 15):
    print(f"   Cargando {farmacia}...")
    productos = []
    base_url = "https://inkafarma.pe" if farmacia == "Inkafarma" else "https://www.mifarma.com.pe"

    try:
        async with async_playwright() as p:
            browser, context = await crear_contexto_navegador(p)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            await page.wait_for_timeout(5000) # Espera para contenido dinámico

            # Scroll más agresivo
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

            content = await page.content()
            await browser.close()

            soup = BeautifulSoup(content, 'html.parser')

            # Múltiples selectores para encontrar 'cards' de productos
            selectors = [
                'div[data-testid="product-card"]', 'article[class*="product"]',
                'div.product-card', 'div.product-item', 'div[class*="ProductCard"]',
                'li.product', 'a[href*="/producto/"]', 'a[href*="/p/"]'
            ]
            cards = []
            for selector in selectors:
                cards.extend(soup.select(selector))

            unique_cards = list(dict.fromkeys(cards)) # Eliminar duplicados
            print(f"   📦 {len(unique_cards)} elementos detectados en {farmacia}")

            seen_urls = set()
            for item in unique_cards:
                try:
                    # 1. ENLACE
                    link_elem = item.find('a', href=True) if item.name != 'a' else item
                    if not link_elem or not link_elem.get('href'):
                        continue

                    href = urljoin(base_url, link_elem['href'].strip())
                    if href in seen_urls or len(href) < len(base_url) + 5:
                        continue
                    seen_urls.add(href)

                    # 2. NOMBRE
                    nombre = ""
                    nombre_elem = item.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'name|title', re.I))
                    if nombre_elem:
                        nombre = nombre_elem.get_text(strip=True)
                    if not nombre or len(nombre) < 3:
                        nombre = link_elem.get_text(strip=True)

                    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
                    if not nombre or len(nombre) < 3:
                        continue

                    # 3. IMAGEN
                    img_elem = item.find('img', src=True)
                    img_url = "No disponible"
                    if img_elem:
                        img_url = urljoin(base_url, img_elem.get('src', 'No disponible'))

                    # 4. PRECIOS
                    precio_oferta = "No disponible"
                    precio_regular = "No disponible"

                    # Precio Regular (tachado)
                    reg_price_elem = item.find(class_=re.compile(r'old|original|list-price|line-through', re.I))
                    if reg_price_elem:
                        precio_regular = limpiar_precio(reg_price_elem.get_text(strip=True))

                    # Precio Oferta (principal)
                    oferta_elem = item.find(class_=re.compile(r'price|precio', re.I))
                    if oferta_elem:
                         # A veces el regular está dentro del mismo div, lo quitamos
                         texto_precio = oferta_elem.get_text(strip=True)
                         if precio_regular != "No disponible":
                             texto_precio = texto_precio.replace(precio_regular.replace("S/ ", ""), "")
                         precio_oferta = limpiar_precio(texto_precio)

                    # Fallback si no se encontró con clase
                    if precio_oferta == "No disponible":
                        precio_match = item.find(string=re.compile(r'S/\s*[\d,\.]+'))
                        if precio_match:
                            precio_oferta = limpiar_precio(precio_match.strip())

                    # Lógica de ajuste
                    if precio_oferta == "No disponible" and precio_regular != "No disponible":
                        precio_oferta = precio_regular
                        precio_regular = "No disponible"
                    if precio_oferta == precio_regular:
                        precio_regular = "No disponible"


                    productos.append({
                        "Producto": nombre,
                        "Precio_Oferta": precio_oferta,
                        "Precio_Regular": precio_regular,
                        "Imagen_URL": img_url,
                        "Enlace": href,
                        "Farmacia": farmacia
                    })

                    if len(productos) >= max_items:
                        break
                except Exception:
                    continue

            print(f"   ✅ {len(productos)} productos extraídos de {farmacia}")
            return productos
    except Exception as e:
        print(f"   ❌ Error en {farmacia}: {e}")
        return []

# =============================================
# SCRAPER BOTICAS PERU
# =============================================
async def scrape_boticasperu_playwright(keyword: str, max_items: int = 15):
    url = f"https://boticasperu.pe/catalogsearch/result/?q={quote_plus(keyword)}"
    print(f"   Cargando BoticasPeru...")
    productos = []
    base_url = "https://boticasperu.pe"

    try:
        async with async_playwright() as p:
            browser, context = await crear_contexto_navegador(p)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)

            await page.wait_for_timeout(3000)
            for _ in range(4):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            content = await page.content()
            await browser.close()

            soup = BeautifulSoup(content, 'html.parser')
            cards = soup.select("li.item.product, div.product-item")
            print(f"   📦 {len(cards)} productos detectados en BoticasPeru")

            seen = set()
            for card in cards:
                try:
                    # 1. ENLACE
                    a_tag = card.find('a', href=True)
                    if not a_tag: continue
                    href = a_tag.get('href', '').strip()
                    if not href or href in seen or '.html' not in href:
                        continue
                    seen.add(href)

                    # 2. NOMBRE
                    nombre_elem = card.find(class_='product-item-link')
                    nombre = nombre_elem.get_text(strip=True) if nombre_elem else a_tag.get_text(strip=True)
                    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
                    if not nombre or len(nombre) < 3:
                        continue

                    # 3. IMAGEN
                    img_elem = card.find('img', class_='product-image-photo')
                    img_url = "No disponible"
                    if img_elem:
                        img_url = img_elem.get('src') or img_elem.get('data-src')
                        img_url = urljoin(base_url, img_url)

                    # 4. PRECIOS (Magento: old-price, special-price, price)
                    precio_oferta = "No disponible"
                    precio_regular = "No disponible"

                    reg_elem = card.find('span', class_='old-price')
                    if reg_elem:
                        precio_regular = limpiar_precio(reg_elem.find('span', class_='price').get_text(strip=True))

                    oferta_elem = card.find('span', class_='special-price')
                    if oferta_elem:
                        precio_oferta = limpiar_precio(oferta_elem.find('span', class_='price').get_text(strip=True))

                    if precio_oferta == "No disponible":
                        norm_elem = card.find('span', class_='price-wrapper', attrs={'data-price-type': 'finalPrice'})
                        if norm_elem:
                            precio_oferta = limpiar_precio(norm_elem.find('span', class_='price').get_text(strip=True))

                    if precio_oferta == "No disponible": # Fallback
                        precio_elem = card.find('span', class_='price')
                        if precio_elem:
                            precio_oferta = limpiar_precio(precio_elem.get_text(strip=True))

                    productos.append({
                        "Producto": nombre,
                        "Precio_Oferta": precio_oferta,
                        "Precio_Regular": precio_regular,
                        "Imagen_URL": img_url,
                        "Enlace": href,
                        "Farmacia": "BoticasPeru"
                    })
                    if len(productos) >= max_items:
                        break
                except Exception:
                    continue
            print(f"   ✅ {len(productos)} productos extraídos de BoticasPeru")
            return productos
    except Exception as e:
        print(f"   ❌ Error en BoticasPeru: {e}")
        return []

# =============================================
# SCRAPER BOTICAS Y SALUD
# =============================================
async def scrape_boticasysalud_playwright(keyword: str, max_items: int = 15):
    url = f"https://www.boticasysalud.com/tienda/busqueda?q={quote_plus(keyword)}"
    print(f"   Cargando Boticas y Salud...")
    productos = []
    base_url = "https://www.boticasysalud.com"

    try:
        async with async_playwright() as p:
            browser, context = await crear_contexto_navegador(p)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)

            await page.wait_for_timeout(5000) # Espera larga para React
            for _ in range(8): # Scroll agresivo
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            content = await page.content()
            await browser.close()
            soup = BeautifulSoup(content, 'html.parser')

            links = soup.find_all('a', href=re.compile(r'/tienda/productos/'))
            print(f"   📦 {len(links)} productos detectados en Boticas y Salud")

            seen = set()
            for link in links:
                try:
                    # 1. ENLACE
                    href = link.get('href', '').strip()
                    if not href or href in seen: continue
                    seen.add(href)
                    href = urljoin(base_url, href)

                    card = link.find_parent('div', class_=re.compile(r'product')) or link

                    # 2. NOMBRE
                    nombre = ""
                    nombre_elem = card.find('div', class_=re.compile(r'product-card__name|product__name'))
                    if nombre_elem:
                        nombre = nombre_elem.get_text(strip=True)
                    if not nombre:
                        nombre = link.get_text(strip=True)
                    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
                    if not nombre or len(nombre) < 3: continue

                    # 3. IMAGEN
                    img_elem = card.find('img', src=True)
                    img_url = "No disponible"
                    if img_elem:
                        img_url = urljoin(base_url, img_elem.get('src') or img_elem.get('data-src'))

                    # 4. PRECIOS
                    precio_oferta = "No disponible"
                    precio_regular = "No disponible"

                    reg_elem = card.find('div', class_=re.compile(r'price-original|old-price|list-price', re.I))
                    if reg_elem:
                        precio_regular = limpiar_precio(reg_elem.get_text(strip=True))

                    oferta_elem = card.find('div', class_=re.compile(r'price|precio'))
                    if oferta_elem:
                        texto_precio = oferta_elem.get_text(strip=True)
                        if precio_regular != "No disponible":
                            texto_precio = texto_precio.replace(precio_regular.replace("S/ ", ""), "")
                        precio_oferta = limpiar_precio(texto_precio)

                    if precio_oferta == "No disponible":
                        precio_match = card.find(string=re.compile(r'S/\s*[\d,\.]+'))
                        if precio_match:
                            precio_oferta = limpiar_precio(precio_match.strip())

                    if precio_oferta == "No disponible" and precio_regular != "No disponible":
                        precio_oferta = precio_regular
                        precio_regular = "No disponible"

                    productos.append({
                        "Producto": nombre,
                        "Precio_Oferta": precio_oferta,
                        "Precio_Regular": precio_regular,
                        "Imagen_URL": img_url,
                        "Enlace": href,
                        "Farmacia": "Boticas y Salud"
                    })
                    if len(productos) >= max_items:
                        break
                except Exception:
                    continue
            print(f"   ✅ {len(productos)} productos extraídos de Boticas y Salud")
            return productos
    except Exception as e:
        print(f"   ❌ Error en Boticas y Salud: {e}")
        return []

# =============================================
# SCRAPER FARMACIA UNIVERSAL
# =============================================
async def scrape_farmaciauniversal_playwright(keyword: str, max_items: int = 15):
    url = f"https://www.farmaciauniversal.com/{quote_plus(keyword)}?_q={quote_plus(keyword)}&map=ft"
    print(f"   Cargando Farmacia Universal...")
    productos = []
    base_url = "https://www.farmaciauniversal.com"

    try:
        async with async_playwright() as p:
            browser, context = await crear_contexto_navegador(p)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)

            await page.wait_for_timeout(6000) # Espera para VTEX
            for _ in range(10): # Scroll intensivo para VTEX
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            content = await page.content()
            await browser.close()
            soup = BeautifulSoup(content, 'html.parser')

            links = soup.find_all('a', href=re.compile(r'/[^/]+/p$'))
            print(f"   📦 {len(links)} productos detectados en Farmacia Universal")

            seen = set()
            for link in links:
                try:
                    # 1. ENLACE
                    href = link.get('href', '').strip()
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    href = urljoin(base_url, href)

                    card = link.find_parent('article') or link

                    # 2. NOMBRE
                    nombre = ""
                    nombre_elem = card.find('span', class_=re.compile(r'productBrand|productName'))
                    if nombre_elem:
                        nombre = nombre_elem.get_text(strip=True)
                    if not nombre:
                        nombre = link.get_text(strip=True)

                    nombre = re.sub(r'(?i)\b(comprar|agregar|ver)\b', '', nombre).strip()
                    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
                    if not nombre or len(nombre) < 3: continue

                    # 3. IMAGEN
                    img_elem = card.find('img', src=True)
                    img_url = "No disponible"
                    if img_elem:
                        img_url = urljoin(base_url, img_elem.get('src') or img_elem.get('data-src'))

                    # 4. PRECIOS (VTEX)
                    precio_oferta = "No disponible"
                    precio_regular = "No disponible"

                    reg_elem = card.find('span', class_=re.compile(r'listPrice|list-price', re.I))
                    if reg_elem:
                        precio_regular = limpiar_precio(reg_elem.get_text(strip=True))

                    # VTEX usa 'currencyInteger' y 'currencyFraction'
                    precio_int = card.find('span', class_=re.compile(r'currencyInteger'))
                    if precio_int:
                        precio_valor = precio_int.get_text(strip=True)
                        precio_frac = card.find('span', class_=re.compile(r'currencyFraction'))
                        if precio_frac:
                            precio_valor += "." + precio_frac.get_text(strip=True)
                        precio_oferta = limpiar_precio(f"S/ {precio_valor}")
                    else: # Fallback
                        precio_match = card.find(string=re.compile(r'S/\s*[\d,\.]+'))
                        if precio_match:
                            precio_oferta = limpiar_precio(precio_match.strip())

                    if precio_oferta == "No disponible" and precio_regular != "No disponible":
                        precio_oferta = precio_regular
                        precio_regular = "No disponible"

                    productos.append({
                        "Producto": nombre,
                        "Precio_Oferta": precio_oferta,
                        "Precio_Regular": precio_regular,
                        "Imagen_URL": img_url,
                        "Enlace": href,
                        "Farmacia": "Farmacia Universal"
                    })
                    if len(productos) >= max_items:
                        break
                except Exception:
                    continue
            print(f"   ✅ {len(productos)} productos extraídos de Farmacia Universal")
            return productos
    except Exception as e:
        print(f"   ❌ Error en Farmacia Universal: {e}")
        return []

# =============================================
# FUNCIÓN PRINCIPAL DE COMPARACIÓN
# =============================================
async def comparar_precios_playwright(keyword: str, max_items: int = 15):
    """Compara precios en las 5 farmacias principales del Perú"""
    url_inka = f"https://inkafarma.pe/buscador?keyword={quote_plus(keyword)}"
    url_mi = f"https://www.mifarma.com.pe/buscador?keyword={quote_plus(keyword)}"

    # Ejecutar todos los scrapers en paralelo
    resultados = await asyncio.gather(
        scrape_farmacia_playwright(url_inka, "Inkafarma", max_items),
        scrape_farmacia_playwright(url_mi, "Mifarma", max_items),
        scrape_boticasperu_playwright(keyword, max_items),
        scrape_boticasysalud_playwright(keyword, max_items),
        scrape_farmaciauniversal_playwright(keyword, max_items)
    )

    # Combinar todos los productos
    todos_productos = []
    for lista_productos in resultados:
        todos_productos.extend(lista_productos)

    return todos_productos