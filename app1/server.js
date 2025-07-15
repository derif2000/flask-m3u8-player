const express = require('express');
const puppeteer = require('puppeteer');
const https = require('https');

const app = express();
app.use(express.static('public'));

function downloadText(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function scrapeM3u8(pageUrl) {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--disable-web-security', '--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();

  let finalM3u8Url = null;

  try {
    console.log(`🌐 Abriendo ${pageUrl}`);
    await page.goto(pageUrl, { waitUntil: 'networkidle2', timeout: 60000 });

    const iframeSrc = await page.evaluate(() => {
      const iframe = document.querySelector('#iframe-holder iframe');
      return iframe?.src || null;
    });

    if (!iframeSrc) throw new Error('No se encontró el iframe');

    console.log(`🔗 Iframe src: ${iframeSrc}`);
    await page.goto(iframeSrc, { waitUntil: 'networkidle2', timeout: 60000 });

    // escuchar las requests en la página del iframe
    const m3u8Urls = new Set();
    page.on('request', request => {
      const url = request.url();
      if (url.includes('.m3u8') && !url.startsWith('blob:')) {
        console.log(`🎯 Capturada URL .m3u8: ${url}`);
        m3u8Urls.add(url);
      }
    });

    // esperar unos segundos para que cargue y se capturen las requests
    await page.waitForTimeout(5000);

    if (m3u8Urls.size === 0) throw new Error('No se capturaron URLs .m3u8');

    // elegir la que contiene master.m3u8 si existe
    finalM3u8Url = [...m3u8Urls].find(u => u.includes('master.m3u8')) || [...m3u8Urls][0];

  } catch (error) {
    console.error("❌ Error:", error.message);
  } finally {
    await browser.close();
  }

  return finalM3u8Url;
}

// Endpoint para scrapear y devolver la URL final del .m3u8
app.get('/get-m3u8', async (req, res) => {
  const pageUrl = req.query.url;
  if (!pageUrl) return res.status(400).json({ error: 'No URL provided' });

  const m3u8 = await scrapeM3u8(pageUrl);
  if (!m3u8) return res.status(500).json({ error: 'Failed to scrape m3u8' });

  res.json({ m3u8 });
});

// Proxy para servir el m3u8 desde tu servidor
app.get('/proxy-m3u8', (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).send('No URL provided');

  https.get(url, (proxiedRes) => {
    res.setHeader('Content-Type', 'application/vnd.apple.mpegurl');
    proxiedRes.pipe(res);
  }).on('error', (err) => {
    res.status(500).send('Error fetching m3u8');
  });
});

app.listen(4500, '0.0.0.0', () => {
  console.log('✅ Servidor corriendo en http://0.0.0.0:4500');
});
