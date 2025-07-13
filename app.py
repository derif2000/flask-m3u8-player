from flask import Flask, request, render_template_string
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

# ⚠️ Importante: Playwright requiere instalar navegadores la primera vez
# En tu local haz: playwright install
# En Render puedes ponerlo como build command: playwright install

def get_best_m3u8(url, timeout=20):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout*1000)

        best_url = None

        # Observa las peticiones mientras carga
        for req in page.context.requests:
            if ".m3u8" in req.url and "blob:" not in req.url:
                best_url = req.url
                print(f"✅ Encontrado: {best_url}")
                break

        browser.close()
        return best_url


@app.route("/")
def index():
    return """
    <h2>✅ Flask M3U8 Player</h2>
    <p>Usa la ruta <code>/ver?url=TU_URL</code> para reproducir.</p>
    """


@app.route("/ver")
def ver():
    original_url = request.args.get("url")
    if not original_url:
        return "Parámetro 'url' faltante", 400

    m3u8_url = get_best_m3u8(original_url)

    if not m3u8_url:
        return "No se encontró un enlace .m3u8", 404

    html = f"""
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
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
