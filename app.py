from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import logging

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Configuración mejorada para entornos de producción
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-setuid-sandbox")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    return driver

def get_best_m3u8(url, timeout=20):
    driver = None
    try:
        driver = get_driver()
        logger.info(f"Accediendo a la URL: {url}")
        driver.get(url)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        found = set()
        start_time = time.time()
        best_url = None

        while time.time() - start_time < timeout:
            logs = driver.get_log("performance")

            for log in logs:
                try:
                    network_log = json.loads(log["message"])["message"]
                    if "Network.request" in network_log["method"]:
                        req = network_log["params"]["request"]
                        if "url" in req:
                            req_url = req["url"]
                            if ".m3u8" in req_url and "blob:" not in req_url:
                                if req_url not in found:
                                    found.add(req_url)
                                    logger.info(f"Encontrado M3U8: {req_url}")
                                    best_url = req_url
                except Exception as e:
                    logger.warning(f"Error procesando log: {str(e)}")
                    continue

            time.sleep(1)

        if best_url:
            logger.info(f"URL M3U8 seleccionada: {best_url}")
        else:
            logger.warning("No se encontró ninguna URL M3U8 válida")

        return best_url

    except Exception as e:
        logger.error(f"Error en get_best_m3u8: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()

@app.route('/get_m3u8', methods=['GET'])
def api_get_m3u8():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "El parámetro 'url' es requerido"}), 400
    
    timeout = request.args.get('timeout', default=20, type=int)
    
    try:
        m3u8_url = get_best_m3u8(url, timeout)
        if m3u8_url:
            return jsonify({"m3u8": m3u8_url})
        else:
            return jsonify({"error": "No se pudo encontrar la URL M3U8"}), 404
    except Exception as e:
        logger.error(f"Error en la API: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route('/ver', methods=['GET'])
def ver():
    """Endpoint alternativo para compatibilidad"""
    return api_get_m3u8()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)