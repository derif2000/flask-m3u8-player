const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({ 
    headless: false,
    args: ['--disable-web-security'] // Disable CORS for blob URLs
  });
  const page = await browser.newPage();
  
  try {
    // 1. Navigate to the page
    await page.goto('https://hgplaycdn.com/e/u0vl5bnc86a6', { 
      waitUntil: 'networkidle2',
      timeout: 60000
    });

    // 2. Wait for JWPlayer to load
    await page.waitForFunction(() => typeof jwplayer === 'function', { timeout: 15000 });

    // 3. Get the video source from JWPlayer
    const m3u8Url = await page.evaluate(() => {
      const player = jwplayer('vplayer');
      if (player && player.getPlaylistItem) {
        const item = player.getPlaylistItem();
        if (item && item.sources && item.sources.length) {
          // Find HLS source
          const hlsSource = item.sources.find(source => 
            source.type === 'hls' || source.file.includes('.m3u8')
          );
          return hlsSource ? hlsSource.file : null;
        }
      }
      return null;
    });

    if (!m3u8Url) throw new Error("No M3U8 URL found in JWPlayer sources");

    // 4. Save the URL
    const filePath = path.join(__dirname, 'm3u8.txt');
    fs.writeFileSync(filePath, m3u8Url);
    console.log("✅ URL saved to:", filePath);

  } catch (error) {
    console.error("❌ Error:", error.message);
    await page.screenshot({ path: 'error.png' });
    console.log("Screenshot saved to error.png");
  } finally {
    await browser.close();
  }
})();