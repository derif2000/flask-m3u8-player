from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import requests
import logging

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    chrome_options = Options()
    
    # Configuración avanzada para evitar detección
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Opciones para evitar bloqueos
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Modificar propiedades del navegador
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    return driver

def extract_m3u8(url, timeout=30):
    driver = get_driver()
    try:
        # Navegar a la página
        driver.get(url)
        time.sleep(5)  # Esperar a que cargue
        
        # Obtener logs de red
        logs = driver.get_log('performance')
        m3u8_urls = []
        
        for entry in logs:
            try:
                log = json.loads(entry['message'])['message']
                if log['method'] == 'Network.responseReceived':
                    response = log['params']['response']
                    if '.m3u8' in response['url']:
                        m3u8_urls.append(response['url'])
            except:
                continue
        
        # Filtrar URLs válidas
        valid_urls = [u for u in m3u8_urls if 'master.m3u8' in u or 'index.m3u8' in u]
        return valid_urls[0] if valid_urls else None
        
    except Exception as e:
        logger.error(f"Error extracting M3U8: {str(e)}")
        return None
    finally:
        driver.quit()

@app.route('/get_stream', methods=['GET'])
def get_stream():
    source_url = request.args.get('url')
    if not source_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        # Extraer URL M3U8
        m3u8_url = extract_m3u8(source_url)
        if not m3u8_url:
            return jsonify({"error": "Could not extract M3U8 URL"}), 404
        
        # Proxy para evitar CORS y 403
        headers = {
            'Referer': source_url,
            'Origin': source_url.split('/')[0] + '//' + source_url.split('/')[2],
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(m3u8_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return Response(
                response.content,
                mimetype='application/vnd.apple.mpegurl',
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Content-Disposition': 'inline'
                }
            )
        else:
            return jsonify({"error": f"Stream server returned {response.status_code}"}), 502
            
    except Exception as e:
        logger.error(f"Error in get_stream: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, ssl_context='adhoc')  # Usar certificado real en producción