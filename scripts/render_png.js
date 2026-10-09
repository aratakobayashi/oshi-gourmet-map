// render_png.js
// venue_guide_images.py から呼ばれる。各フォルダの illust.svg → illust.png、thumb.html → thumb.png（1200x675）を書き出す。
// 使い方: PW_CHROME=<chromium の実行ファイル> NODE_PATH=<playwright のある node_modules> node scripts/render_png.js <フォルダ>...
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const page = await browser.newPage({ viewport: { width: 1200, height: 675 } });
  for (const dir of process.argv.slice(2)) {
    const abs = path.resolve(dir);
    await page.goto('file://' + path.join(abs, 'illust.svg'));
    await page.screenshot({ path: path.join(abs, 'illust.png'), clip: { x: 0, y: 0, width: 1200, height: 675 } });
    await page.goto('file://' + path.join(abs, 'thumb.html'));
    await page.waitForTimeout(300);
    await (await page.$('#t')).screenshot({ path: path.join(abs, 'thumb.png') });
  }
  await browser.close();
})();
