from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json

app = Flask(__name__)
CORS(app)  # Habilita CORS

@app.route('/get_m3u8')
def get_m3u8():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(
        service=Service(executable_path='/usr/bin/chromedriver'),
        options=chrome_options
    )
    
    try:
        driver.get(url)
        time.sleep(5)  # Espera a que cargue la página
        
        m3u8_url = None
        logs = driver.get_log('performance')
        
        for log in logs:
            try:
                message = json.loads(log['message'])['message']
                if message['method'] == 'Network.responseReceived':
                    url = message['params']['response']['url']
                    if '.m3u8' in url:
                        m3u8_url = url
                        break
            except:
                continue
                
        return jsonify({'m3u8': m3u8_url}) if m3u8_url else jsonify({'error': 'M3U8 not found'}), 404
    finally:
        driver.quit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)