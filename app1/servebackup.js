const express = require('express');
const puppeteer = require('puppeteer');
const https = require('https');
const path = require('path');

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
    args: ['--disable-web-security']
  });
  const page = await browser.newPage();

  let finalM3u8Url = null;

  try {
    await page.goto(pageUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    await page.waitForFunction(() => typeof jwplayer === 'function', { timeout: 15000 });

    const relativeMaster = await page.evaluate(() => {
      const player = jwplayer('vplayer');
      if (player && player.getPlaylistItem) {
        const item = player.getPlaylistItem();
        if (item && item.file) return item.file;
      }
      return null;
    });

    const base = new URL(page.url());
    const masterUrl = `${base.origin}${relativeMaster}`;
    const masterContent = await downloadText(masterUrl);
    const variant = masterContent.split('\n').find(line => line.trim().endsWith('.m3u8'));

    finalM3u8Url = new URL(variant, masterUrl).href;

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
