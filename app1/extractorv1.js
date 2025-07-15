const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const https = require('https');

// Configuración
const DEBUG = true;
const MAX_SEGMENTS_TO_DOWNLOAD = 3; // Para pruebas
const OUTPUT_DIR = path.join(__dirname, 'output');

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR);

async function downloadFile(url, referer) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: { 'Referer': referer, 'User-Agent': 'Mozilla/5.0' },
      timeout: 30000
    };

    if (DEBUG) console.log(`🔽 Descargando: ${url}`);

    const req = https.get(url, options, (res) => {
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }

      const data = [];
      res.on('data', chunk => data.push(chunk));
      res.on('end', () => {
        const buffer = Buffer.concat(data);
        resolve({
          content: buffer,
          contentType: res.headers['content-type'],
          finalUrl: res.responseUrl || url
        });
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Timeout'));
    });
  });
}

async function extractMediaUrls(content, baseUrl) {
  const result = { segments: [], variants: [] };

  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith('#EXT-X-STREAM-INF')) {
      const nextLine = lines[i + 1]?.trim();
      if (nextLine && !nextLine.startsWith('#')) {
        result.variants.push(new URL(nextLine, baseUrl).href);
      }
    } else if (line.startsWith('#EXTINF') && lines[i + 1]?.trim()) {
      const mediaUrl = lines[i + 1].trim();
      if (mediaUrl.endsWith('.ts') || mediaUrl.endsWith('.jpg')) {
        result.segments.push(new URL(mediaUrl, baseUrl).href);
      }
    }
  }

  return result;
}

async function processMasterTxt(masterUrl, referer) {
  try {
    const { content, finalUrl } = await downloadFile(masterUrl, referer);
    const contentStr = content.toString();

    if (DEBUG) {
      fs.writeFileSync(path.join(OUTPUT_DIR, 'master_raw.txt'), contentStr);
      console.log('📄 Master.txt descargado y guardado');
    }

    const baseUrl = new URL(finalUrl).origin;
    const mediaInfo = await extractMediaUrls(contentStr, finalUrl);

    if (mediaInfo.segments.length > 0) {
      console.log(`🎬 Encontrados ${mediaInfo.segments.length} segmentos`);
      return { type: 'segments', segments: mediaInfo.segments, baseUrl };
    } else if (mediaInfo.variants.length > 0) {
      console.log(`🔄 Encontradas ${mediaInfo.variants.length} variantes`);
      const variantUrl = mediaInfo.variants[0];
      return await processMasterTxt(variantUrl, referer);
    } else {
      throw new Error('No se encontraron segmentos ni variantes en el archivo');
    }
  } catch (error) {
    console.error('❌ Error procesando master.txt:', error.message);
    throw error;
  }
}

(async () => {
  const browser = await puppeteer.launch({
    headless: false,
    args: ['--disable-web-security']
  });
  const page = await browser.newPage();

  try {
    // Paso 1: Cargar la página principal
    await page.goto('https://filemoon.sx/e/m3vfqqaem47v', {
      waitUntil: 'networkidle2',
      timeout: 60000
    });

    console.log("🌐 Página principal cargada:", page.url());

    // Paso 2: Obtener src del iframe
    const iframeUrl = await page.$eval('#iframe-holder iframe', el => el.src);
    if (!iframeUrl) throw new Error("No se encontró el iframe en la página");

    console.log("🔗 URL del iframe:", iframeUrl);

    // Paso 3: Abrir nueva página para el iframe
    const iframePage = await browser.newPage();

    // Paso 4: Interceptar requests
    const m3u8Urls = [];
    iframePage.on('response', async (response) => {
      const url = response.url();
      if (url.includes('.m3u8')) {
        m3u8Urls.push(url);
        console.log(`🎯 Capturada URL .m3u8: ${url}`);
      }
    });

    await iframePage.goto(iframeUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    console.log("🌐 Página del iframe cargada:", iframePage.url());

    // Esperar unos segundos para que se carguen las requests
    await new Promise(r => setTimeout(r, 5000));

    if (m3u8Urls.length === 0) throw new Error("No se detectó ninguna URL .m3u8 en las peticiones de red");

    // Elegir la primera que termine en master.m3u8 o la primera en general
    let masterUrl = m3u8Urls.find(u => u.includes('master.m3u8')) || m3u8Urls[0];
    console.log(`✅ Usando master.m3u8: ${masterUrl}`);

    // Paso 5: Procesar master.txt y obtener segmentos
    const { segments } = await processMasterTxt(masterUrl, iframePage.url());

    const playlistContent = [
      '#EXTM3U',
      '#EXT-X-VERSION:3',
      '#EXT-X-TARGETDURATION:10',
      '#EXT-X-MEDIA-SEQUENCE:1',
      ...segments.map(seg => `#EXTINF:10.010,\n${seg}`),
      '#EXT-X-ENDLIST'
    ].join('\n');

    const playlistPath = path.join(OUTPUT_DIR, 'playlist_final.m3u8');
    fs.writeFileSync(playlistPath, playlistContent);
    console.log("✅ Playlist final generada:", playlistPath);

    if (DEBUG && segments.length > 0) {
      const segmentsDir = path.join(OUTPUT_DIR, 'segments');
      if (!fs.existsSync(segmentsDir)) fs.mkdirSync(segmentsDir);

      for (let i = 0; i < Math.min(segments.length, MAX_SEGMENTS_TO_DOWNLOAD); i++) {
        try {
          console.log(`⬇️ Descargando segmento ${i + 1}`);
          const { content } = await downloadFile(segments[i], iframePage.url());
          const ext = segments[i].endsWith('.ts') ? '.ts' : '.jpg';
          fs.writeFileSync(path.join(segmentsDir, `segment_${i}${ext}`), content);
        } catch (error) {
          console.error(`⚠️ Error descargando segmento ${i}:`, error.message);
        }
      }
    }

  } catch (error) {
    console.error("❌ Error en el proceso principal:", error.message);
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'error.png') });
    console.log("📸 Captura guardada en error.png");
  } finally {
    await browser.close();
  }
})();
