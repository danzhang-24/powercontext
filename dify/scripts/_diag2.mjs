import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1280, height: 2400 } });
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 }).catch(()=>{});
await p.waitForTimeout(6000);
const out = await p.evaluate(() => {
  const res = {};
  res.bodyTextContent = document.body.textContent.length;
  res.bodyInnerText = document.body.innerText.length;
  const sel = ["#root .ne-body", ".ne-body", ".lake-content", "[class*=ne-body]", "[class*=lake]", "[class*=doc-reader]", "[class*=reader]", "article"];
  for (const s of sel) {
    const el = document.querySelector(s);
    if (el) res[s] = { len: el.textContent.length, cls: el.className?.toString?.().slice(0,80) };
  }
  return res;
});
console.log(JSON.stringify(out, null, 1));
await b.close();
