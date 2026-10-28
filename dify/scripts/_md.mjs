import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage","--enable-features=ClipboardAPI"] });
const ctx = await b.newContext({ viewport: { width: 1400, height: 1200 }, permissions: ["clipboard-read", "clipboard-write"] });
const p = await ctx.newPage();
await p.goto(process.argv[2], { waitUntil: "networkidle", timeout: 90000 });
await p.waitForTimeout(4000);
const btn = p.locator('[data-testid="ViewerHeader:doc-action-copyMarkdown"]');
try {
  await btn.click({ timeout: 8000, force: true });
  await p.waitForTimeout(2500);
  const md = await p.evaluate(async () => { try { return await navigator.clipboard.readText(); } catch (e) { return "CLIP_ERR:" + String(e).slice(0,120); } });
  console.log(md);
} catch (e) { console.log("ERR", String(e).slice(0, 300)); }
await b.close();
