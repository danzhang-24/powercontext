import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage();
const seen = new Set();
p.on("request", (r) => {
  const u = r.url();
  if (u.includes("yuque.com") && !seen.has(u)) { seen.add(u); console.log("REQ", r.method(), u.slice(0,200)); }
});
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(8000);
await b.close();
