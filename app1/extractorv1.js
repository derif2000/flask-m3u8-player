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

    if (!relativeMaster) throw new Error("No file found from jwplayer");

    let masterUrl;

    // ✅ Si ya es absoluta, úsala tal cual
    if (/^https?:\/\//i.test(relativeMaster)) {
      masterUrl = relativeMaster;
    } else {
      const base = new URL(page.url());
      masterUrl = `${base.origin}${relativeMaster}`;
    }

    console.log(`🎬 Master M3U8 URL: ${masterUrl}`);

    const masterContent = await downloadText(masterUrl);

    if (masterContent.includes('#EXTM3U')) {
      const variant = masterContent
        .split('\n')
        .find(line => line.trim().endsWith('.m3u8'));

      if (variant) {
        finalM3u8Url = new URL(variant, masterUrl).href;
      } else {
        finalM3u8Url = masterUrl;
      }
    } else {
      throw new Error("Downloaded file is not a valid m3u8 playlist");
    }

  } catch (error) {
    console.error("❌ Error:", error.message);
  } finally {
    await browser.close();
  }

  return finalM3u8Url;
}

app.get('/get-m3u8', async (req, res) => {
  const pageUrl = req.query.url;
  if (!pageUrl) return res.status(400).json({ error: 'No URL provided' });

  const m3u8 = await scrapeM3u8(pageUrl);
  if (!m3u8) return res.status(500).json({ error: 'Failed to scrape m3u8' });

  res.json({ m3u8 });
});

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
