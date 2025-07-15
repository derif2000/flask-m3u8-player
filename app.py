from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import logging

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todos los dominios

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_m3u8_url(target_url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            formats = info.get('formats', [])
            
            # Filtrar formatos HLS/M3U8
            m3u8_formats = [
                f for f in formats 
                if f.get('protocol') in ('m3u8', 'm3u8_native')
            ]
            
            if not m3u8_formats:
                return None
                
            # Seleccionar la mejor calidad
            best_format = max(m3u8_formats, key=lambda x: x.get('height', 0))
            return best_format['url']
            
    except Exception as e:
        logger.error(f"Error al extraer M3U8: {str(e)}")
        return None

@app.route('/extract', methods=['POST'])
def extract_m3u8():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL parameter is required"}), 400
    
    target_url = data['url'].strip()
    m3u8_url = get_m3u8_url(target_url)
    
    if m3u8_url:
        return jsonify({
            "success": True,
            "stream_url": m3u8_url
        })
    return jsonify({
        "success": False,
        "error": "No se pudo extraer el enlace M3U8"
    }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)