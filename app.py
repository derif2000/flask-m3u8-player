from flask import Flask, request, render_template_string
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json

app = Flask(__name__)

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--ignore-certificate-errors")

    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def get_best_m3u8(url, timeout=20):
    driver = get_driver()
    driver.get(url)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    found = set()
    best_url = None
    start_time = time.time()

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
                                print(f"🔷 Encontrado: {req_url}")
                                best_url = req_url
            except Exception:
                continue

        if best_url:
            break

        time.sleep(1)

    driver.quit()
    return best_url


@app.route("/ver")
def ver():
    original_url = request.args.get("url")
    if not original_url:
        return "Falta parámetro ?url=", 400

    m3u8_url = get_best_m3u8(original_url)

    if not m3u8_url:
        return "No se encontró ningún .m3u8", 404

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
    <meta charset="UTF-8">
    <title>Reproductor HLS</title>
    </head>
    <body>
    <h2>Reproductor HLS</h2>
    <video id="video" controls autoplay style="width:80%;max-width:800px;"></video>

    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
      const video = document.getElementById('video');
      const m3u8Url = '{m3u8_url}';

      if (Hls.isSupported()) {{
        const hls = new Hls();
        hls.loadSource(m3u8Url);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, function () {{
          video.play();
        }});
      }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
        video.src = m3u8Url;
        video.addEventListener('loadedmetadata', function () {{
          video.play();
        }});
      }} else {{
        alert("Tu navegador no soporta HLS.");
      }}
    </script>
    </body>
    </html>
    """

    return render_template_string(html)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
