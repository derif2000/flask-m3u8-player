from flask import Flask, render_template_string, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json, time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Mi Reproductor HLS</title>
</head>
<body>
<h2>Reproductor HLS</h2>
<video id="video" controls autoplay style="width: 80%; max-width: 800px;"></video>

<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
  const video = document.getElementById('video');
  const m3u8Url = '{{ m3u8_url }}';

  if (Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource(m3u8Url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
      video.play();
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = m3u8Url;
    video.addEventListener('loadedmetadata', function () {
      video.play();
    });
  } else {
    alert("Tu navegador no soporta HLS.");
  }
</script>
</body>
</html>
"""

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


@app.route("/ver")
def ver():
    origen = request.args.get("url")
    if not origen:
        return "Falta parámetro ?url=", 400

    m3u8_url = get_best_m3u8(origen)
    if not m3u8_url:
        return "No se pudo obtener el stream", 500

    return render_template_string(HTML_TEMPLATE, m3u8_url=m3u8_url)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
