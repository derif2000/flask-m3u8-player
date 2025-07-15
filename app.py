from flask import Flask, request, jsonify
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

app = Flask(__name__)
# Configuración más robusta de CORS
CORS(app, resources={
    r"/get_m3u8": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")  # Nueva sintaxis para headless
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--mute-audio")
    
    # Mejores prácticas para Selenium 4+
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Configuración de logs
    options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver

def get_best_m3u8(url, timeout=40):
    driver = None
    try:
        driver = get_driver()
        logger.info(f"Navegando a: {url}")
        driver.get(url)
        
        # Esperar a que la página cargue algo de contenido
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        found_urls = set()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            logs = driver.get_log("performance")
            
            for log in logs:
                try:
                    message = json.loads(log["message"])["message"]
                    if message["method"] == "Network.requestWillBeSent":
                        request = message["params"]["request"]
                        url = request.get("url", "")
                        if ".m3u8" in url and "blob:" not in url:
                            if url not in found_urls:
                                logger.info(f"Encontrado M3U8: {url}")
                                found_urls.add(url)
                except Exception as e:
                    logger.error(f"Error procesando log: {e}")
                    continue
            
            # Scroll para activar posibles cargas lazy
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
        
        # Devolver la mejor URL (podrías añadir lógica para seleccionar la de mayor calidad)
        return found_urls.pop() if found_urls else None
        
    except Exception as e:
        logger.error(f"Error en get_best_m3u8: {e}")
        return None
    finally:
        if driver:
            driver.quit()

@app.route("/get_m3u8", methods=["POST", "OPTIONS"])
def api_get_m3u8():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    
    try:
        data = request.get_json(silent=True)
        if not data or "url" not in data:
            return jsonify({"error": "URL no proporcionada"}), 400
        
        url = data["url"]
        logger.info(f"Solicitud recibida para URL: {url}")
        
        m3u8_url = get_best_m3u8(url, timeout=40)
        
        if m3u8_url:
            response = jsonify({"m3u8": m3u8_url})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
        else:
            return jsonify({"error": "No se encontró ningún stream M3U8"}), 404
            
    except Exception as e:
        logger.error(f"Error en la API: {str(e)}")
        return jsonify({"error": str(e)}), 500

def _build_cors_preflight_response():
    response = jsonify({"success": True})
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST")
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)