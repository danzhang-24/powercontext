import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1400, height: 1600 } });
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(5000);
const html = await p.evaluate(() => {
  const el = document.querySelector(".main-wrapper") || document.body;
  return el.innerHTML.slice(0, 6000);
});
console.log(html);
await b.close();
