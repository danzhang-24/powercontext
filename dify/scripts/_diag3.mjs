import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1400, height: 1800 } });
const url = process.argv[2];
await p.goto(url, { waitUntil: "networkidle", timeout: 90000 }).catch(e=>console.log("nav err", String(e).slice(0,120)));
await p.waitForTimeout(7000);
console.log("TITLE:", await p.title());
console.log("URL:", p.url());
let last=0;
for (let i=0;i<40;i++){ await p.mouse.wheel(0,1400); await p.waitForTimeout(400);
  const len = await p.evaluate(()=>document.body.innerText.length); if(len===last && i>3) break; last=len; }
console.log("----- TEXT -----");
console.log(await p.evaluate(()=>document.body.innerText));
await p.screenshot({ path: "/workspace/pc/dify/ob.png", fullPage: false });
await b.close();
