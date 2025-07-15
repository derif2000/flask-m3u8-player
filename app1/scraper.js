const puppeteer = require('puppeteer');
const https = require('https');

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

module.exports = scrapeM3u8;
