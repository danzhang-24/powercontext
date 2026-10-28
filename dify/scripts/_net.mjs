import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage();
const hits = [];
p.on("response", async (r) => {
  const u = r.url();
  if (!u.includes("yuque.com") && !u.includes("alicdn")) return;
  const ct = r.headers()["content-type"] || "";
  if (!ct.includes("json")) return;
  const len = Number(r.headers()["content-length"] || 0);
  if (len < 2000) return;
  hits.push({ u: u.slice(0, 220), len, status: r.status() });
});
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(6000);
for (const h of hits) console.log(h.status, h.len, h.u);
await b.close();
