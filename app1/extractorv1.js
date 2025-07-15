const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const https = require('https');

function downloadText(url, referer) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: {
        'Referer': referer,
        'User-Agent': 'Mozilla/5.0'
      }
    };
    https.get(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

(async () => {
  const browser = await puppeteer.launch({ 
    headless: false,
    args: ['--disable-web-security']
  });
  const page = await browser.newPage();

  try {
    await page.goto('https://movearnpre.com/file/xj1j05poxbhw', { 
      waitUntil: 'networkidle2',
      timeout: 60000
    });

    console.log("🌐 Página cargada:", page.url());

    await page.waitForFunction(() => typeof jwplayer === 'function', { timeout: 15000 });

    console.log("🎥 JWPlayer detectado");

    const relativeMaster = await page.evaluate(() => {
      const player = jwplayer('vplayer');
      if (player && player.getPlaylistItem) {
        const item = player.getPlaylistItem();
        if (item && item.file) {
          return item.file; // ruta (puede ser relativa o absoluta)
        }
      }
      return null;
    });

    if (!relativeMaster) throw new Error("No se encontró master.m3u8 en JWPlayer");

    const base = new URL(page.url());
    const masterUrl = new URL(relativeMaster, base).href;

    console.log("🎬 Master M3U8 URL:", masterUrl);

    // descargar el master.m3u8
    console.log("⬇️ Descargando master.m3u8…");
    const masterContent = await downloadText(masterUrl, page.url());
    console.log("📄 Contenido de master.m3u8:\n", masterContent);

    // buscar la primera línea que sea otra m3u8
    const lines = masterContent.split('\n');
    const variant = lines.find(line => line.trim().includes('.m3u8'));

    if (!variant) throw new Error("No se encontró ninguna variante en master.m3u8");

    const finalM3u8Url = new URL(variant.trim(), masterUrl).href;
    console.log("✅ Variante encontrada:", finalM3u8Url);

    const txtPath = path.join(__dirname, 'm3u8_final.txt');
    fs.writeFileSync(txtPath, finalM3u8Url);
    console.log("✅ URL final guardada en:", txtPath);

  } catch (error) {
    console.error("❌ Error:", error.message);
    await page.screenshot({ path: 'error.png' });
    console.log("📸 Captura guardada en error.png");
  } finally {
    await browser.close();
  }
})();
