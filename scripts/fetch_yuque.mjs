// 抓语雀文档正文(服务端渲染的 SPA,用无头浏览器取 innerText)
import { chromium } from "playwright";
const urls = process.argv.slice(2);
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
for (const url of urls) {
  const p = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  try {
    await p.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
    await p.waitForTimeout(5000);
    const txt = await p.evaluate(() => {
      const el = document.querySelector(".ne-body, .lake-content, .doc-reader, article, main, .content") || document.body;
      return el.innerText;
    });
    console.log(`\n\n=============== ${url} ===============`);
    console.log(txt);
  } catch (e) { console.log(`ERR ${url}: ${String(e).slice(0,200)}`); }
  await p.close();
}
await b.close();
