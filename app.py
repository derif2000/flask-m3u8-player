from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

app = Flask(__name__)

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    return driver

def get_best_m3u8(url, timeout=20):
    driver = get_driver()
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
                                best_url = req_url
            except Exception:
                continue

        if best_url:
            break

        time.sleep(1)

    driver.quit()
    return best_url

@app.route("/get_m3u8")
def get_m3u8():
    original_url = request.args.get("url")
    if not original_url:
        return jsonify({"error": "Missing url parameter"}), 400
    m3u8_url = get_best_m3u8(original_url)
    if m3u8_url:
        return jsonify({"m3u8": m3u8_url})
    else:
        return jsonify({"error": "No m3u8 found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)