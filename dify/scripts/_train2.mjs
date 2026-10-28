import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });
const p = await b.newPage({ viewport: { width: 1500, height: 1500 } });
const apis = new Set();
p.on("response", (r) => { const u=r.url(); if (u.includes("/api/")||u.includes("question")) apis.add(r.request().method()+" "+u.slice(0,180)); });
await p.goto("https://open.oceanbase.com/train/detail/21?questionId=600069", { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(3000);
try {
  await p.getByText("seekdb 题目", { exact: true }).first().click({ timeout: 8000 });
  await p.waitForTimeout(4000);
} catch(e) { console.log("click err", String(e).slice(0,120)); }
await p.waitForTimeout(3000);
console.log("URL:", p.url());
console.log("--- APIs ---"); [...apis].slice(0,25).forEach(a=>console.log(a));
console.log("--- TEXT ---");
console.log(await p.evaluate(()=>document.body.innerText));
await b.close();
