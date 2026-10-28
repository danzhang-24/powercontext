import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1280, height: 1400 } });
const url = process.argv[2];
await p.goto(url, { waitUntil: "networkidle", timeout: 90000 }).catch(e=>console.log("nav:", String(e).slice(0,100)));
await p.waitForTimeout(8000);
console.log("TITLE:", await p.title());
console.log("URL:", p.url());
const info = await p.evaluate(() => {
  const cands = [...document.querySelectorAll("div,article,main,section")]
    .map(e => ({ cls: e.className?.toString?.().slice(0,60), len: (e.innerText||"").trim().length }))
    .filter(x => x.len > 300)
    .sort((a,b)=>b.len-a.len).slice(0,6);
  return { bodyLen: document.body.innerText.length, cands };
});
console.log(JSON.stringify(info, null, 1));
await p.screenshot({ path: "/workspace/pc/dify/yq.png", fullPage: false });
await b.close();
