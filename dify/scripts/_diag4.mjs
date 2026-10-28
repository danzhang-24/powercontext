import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1400, height: 2000 } });
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(6000);
const info = await p.evaluate(() => {
  const out = [];
  for (const e of document.querySelectorAll("div,article,section,main")) {
    const tc = (e.textContent||"").trim();
    if (tc.length > 2000) out.push({ cls: (e.className||"").toString().slice(0,70), tag: e.tagName, len: tc.length, kids: e.children.length });
  }
  return out.sort((a,b)=>b.len-a.len).slice(0,8);
});
console.log(JSON.stringify(info,null,1));
await b.close();
