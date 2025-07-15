from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import logging
import traceback
from urllib.parse import urlparse

app = Flask(__name__)

# Configuración avanzada de CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 86400
    }
})

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SeleniumManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls._initialize_driver()
        return cls._instance
    
    @classmethod
    def _initialize_driver(cls):
        options = webdriver.ChromeOptions()
        
        # Configuración de opciones para headless
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--mute-audio")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Configuración de logs y capacidades
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        
        # Configuración experimental
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Inicialización del driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Configuración adicional del navegador
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        
        return driver

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def extract_m3u8_urls(logs):
    m3u8_urls = set()
    for log in logs:
        try:
            message = json.loads(log["message"])["message"]
            if message["method"] == "Network.requestWillBeSent":
                request = message["params"]["request"]
                url = request.get("url", "")
                if (".m3u8" in url.lower() and 
                    not url.startswith("blob:") and 
                    not url.startswith("data:") and
                    is_valid_url(url)):
                    m3u8_urls.add(url)
        except Exception as e:
            logger.debug(f"Error procesando log: {str(e)}")
            continue
    return m3u8_urls

def get_best_m3u8(url, timeout=30):
    driver = None
    try:
        if not is_valid_url(url):
            raise ValueError("URL no válida")
        
        driver = SeleniumManager.get_instance()
        logger.info(f"Iniciando extracción para: {url}")
        
        # Navegar a la URL
        driver.get(url)
        
        # Esperar a que la página cargue
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        found_urls = set()
        start_time = time.time()
        scroll_position = 0
        
        while time.time() - start_time < timeout:
            # Scroll para activar carga de contenido
            scroll_position += 500
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            
            # Obtener logs de red
            logs = driver.get_log("performance")
            new_urls = extract_m3u8_urls(logs)
            
            for new_url in new_urls:
                if new_url not in found_urls:
                    logger.info(f"URL M3U8 encontrada: {new_url}")
                    found_urls.add(new_url)
            
            time.sleep(1)
        
        # Seleccionar la mejor URL (aquí puedes implementar tu lógica de selección)
        return max(found_urls, key=len) if found_urls else None
        
    except Exception as e:
        logger.error(f"Error en get_best_m3u8: {str(e)}\n{traceback.format_exc()}")
        return None
    finally:
        if driver:
            # No cerramos el driver para reutilizarlo
            pass

@app.route("/get_m3u8", methods=["POST", "OPTIONS"])
def api_get_m3u8():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response

    try:
        # Validar contenido JSON
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 415
        
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "Se requiere el parámetro 'url'"}), 400
        
        url = data["url"].strip()
        logger.info(f"Solicitud recibida para URL: {url}")
        
        # Validar URL
        if not is_valid_url(url):
            return jsonify({"error": "URL no válida"}), 400
        
        # Extraer URL M3U8
        m3u8_url = get_best_m3u8(url)
        
        if m3u8_url:
            response = jsonify({
                "success": True,
                "m3u8": m3u8_url,
                "message": "URL M3U8 encontrada"
            })
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
        else:
            return jsonify({
                "success": False,
                "error": "No se encontró ninguna URL M3U8 válida"
            }), 404
            
    except Exception as e:
        logger.error(f"Error en la API: {str(e)}\n{traceback.format_exc()}")
        response = jsonify({
            "success": False,
            "error": "Error interno del servidor",
            "details": str(e)
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "version": "1.0.0"})

if __name__ == "__main__":
    # Configuración para producción
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)