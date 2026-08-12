const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const base = __dirname;
  const out = path.join(base, 'output');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 2400, height: 1600 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(base, 'index.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(700);
  const nodes = await page.locator('.poster').all();
  for (let i = 0; i < nodes.length; i++) {
    const id = await nodes[i].getAttribute('id') || `poster-${i+1}`;
    await nodes[i].screenshot({ path: path.join(out, `${String(i+1).padStart(2,'0')}-${id}.png`) });
  }
  await browser.close();
})();
