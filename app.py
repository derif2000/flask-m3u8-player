import os
import time
import json
import logging
import traceback
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configuración inicial
app = Flask(__name__)

# Configuración avanzada de CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "max_age": 86400
    }
})

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Thread pool para ejecuciones asíncronas
executor = ThreadPoolExecutor(max_workers=4)

class SeleniumManager:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._initialize_driver()
            return cls._instance
    
    @classmethod
    def _initialize_driver(cls):
        options = webdriver.ChromeOptions()
        
        # Optimizaciones de rendimiento
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--log-level=3")
        
        # Cache y red
        options.add_argument("--disk-cache-dir=/tmp/chrome_cache")
        options.add_argument("--media-cache-size=52428800")
        
        # User-Agent moderno
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Configuración de red
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        options.set_capability("pageLoadStrategy", "eager")
        
        # Configuración del servicio
        service = Service(
            ChromeDriverManager().install(),
            service_args=['--verbose'],
            port=12345
        )
        
        try:
            driver = webdriver.Chrome(service=service, options=options)
            # Timeouts explícitos
            driver.set_page_load_timeout(25)
            driver.set_script_timeout(20)
            return driver
        except Exception as e:
            logger.error(f"Error inicializando ChromeDriver: {str(e)}")
            raise

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
                    not url.startswith(("blob:", "data:")) and
                    is_valid_url(url)):
                    m3u8_urls.add(url)
        except Exception:
            continue
    return m3u8_urls

def process_page(driver, url, timeout):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        found_urls = set()
        start_time = time.time()
        scroll_position = 0
        
        while time.time() - start_time < timeout:
            scroll_position += 500
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            
            logs = driver.get_log("performance")
            new_urls = extract_m3u8_urls(logs)
            found_urls.update(new_urls)
            
            if len(found_urls) >= 3:  # Si encontramos varias URLs, salir temprano
                break
                
            time.sleep(0.5)
        
        return sorted(found_urls, key=len, reverse=True)
    except TimeoutException:
        logger.warning("Timeout en carga de página, continuando con lo disponible")
        return list(found_urls)
    except Exception as e:
        logger.error(f"Error procesando página: {str(e)}")
        return []

@app.route("/get_m3u8", methods=["POST", "OPTIONS"])
def api_get_m3u8():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response

    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 415
        
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "Se requiere el parámetro 'url'"}), 400
        
        url = data["url"].strip()
        if not is_valid_url(url):
            return jsonify({"error": "URL no válida"}), 400
        
        logger.info(f"Iniciando procesamiento para: {url}")
        
        # Ejecutar en el thread pool
        future = executor.submit(
            process_page, 
            SeleniumManager.get_instance(), 
            url, 
            30  # timeout
        )
        urls = future.result(timeout=35)  # Timeout mayor que el de Selenium
        
        if urls:
            best_url = urls[0]
            logger.info(f"URL encontrada: {best_url}")
            return jsonify({
                "success": True,
                "m3u8": best_url,
                "alternatives": urls[1:] if len(urls) > 1 else []
            })
        else:
            return jsonify({
                "success": False,
                "error": "No se encontraron URLs M3U8"
            }), 404
            
    except TimeoutException:
        logger.error("Timeout en la ejecución del worker")
        return jsonify({
            "success": False,
            "error": "El servidor tardó demasiado en responder"
        }), 504
    except Exception as e:
        logger.error(f"Error en la API: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "selenium": "active" if SeleniumManager._instance else "inactive"
    })

@app.route("/stats", methods=["GET"])
def stats():
    return jsonify({
        "thread_pool": {
            "active_threads": executor._work_queue.qsize(),
            "max_workers": executor._max_workers
        }
    })

def cleanup():
    if SeleniumManager._instance:
        SeleniumManager._instance.quit()
        SeleniumManager._instance = None

import atexit
atexit.register(cleanup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Configuración para desarrollo (usar gunicorn en producción)
    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )