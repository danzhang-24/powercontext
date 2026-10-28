import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1500, height: 1500 } });
await p.goto("https://open.oceanbase.com/train/detail/21?questionId=600069", { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(4000);
// 抓侧边栏链接
const links = await p.evaluate(() => [...document.querySelectorAll("a")].map(a => ({ t: a.innerText.trim(), h: a.getAttribute("href") })).filter(x => x.t));
console.log(JSON.stringify(links.slice(0, 40), null, 0).replace(/\},\{/g, "},\n{"));
await b.close();
