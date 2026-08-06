const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const assets = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch({ headless: true });
  for (const asset of assets) {
    const page = await browser.newPage({ viewport: { width: asset.width, height: asset.height }, deviceScaleFactor: 1 });
    await page.goto('file://' + asset.source);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: asset.target, clip: { x: 0, y: 0, width: asset.width, height: asset.height }, omitBackground: false });
    await page.close();
  }
  await browser.close();
})();
