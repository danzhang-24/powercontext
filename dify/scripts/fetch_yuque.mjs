/**
 * 抓语雀文档全文。
 * 语雀正文是虚拟渲染的:只有视口附近的 DOM 存在,滚动时旧节点会被回收,
 * 所以必须逐屏滚动并累积「叶子节点文本」(去重),而不是最后一次性取 innerText。
 */
import { chromium } from "playwright";

const urls = process.argv.slice(2);
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/chromium", args: ["--no-sandbox","--disable-dev-shm-usage"] });

for (const url of urls) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1400 } });
  try {
    await p.goto(url, { waitUntil: "networkidle", timeout: 90000 });
    await p.waitForTimeout(3500);
    const acc = new Map();
    const grab = async () => {
      const leaves = await p.evaluate(() => {
        const out = [];
        for (const e of document.querySelectorAll("p,td,th,li,h1,h2,h3,h4,h5,span,div,code,pre,a")) {
          if (e.children.length === 0) {
            const t = (e.textContent || "").replace(/\s+/g, " ").trim();
            if (t) out.push(t);
          }
        }
        return out;
      });
      for (const t of leaves) if (!acc.has(t)) acc.set(t, true);
      return leaves.length;
    };
    let lastCount = -1;
    for (let i = 0; i < 60; i++) {
      const n = await grab();
      await p.mouse.wheel(0, 1000);
      await p.waitForTimeout(300);
      if (n === lastCount && acc.size > 0 && i > 6) {
        await grab();
        break;
      }
      lastCount = n;
    }
    await p.waitForTimeout(800);
    await grab();
    console.log(`\n\n=============== ${url} ===============\n`);
    console.log([...acc.keys()].join("\n"));
  } catch (e) {
    console.log(`ERR ${url}: ${String(e).slice(0, 200)}`);
  }
  await p.close();
}
await b.close();
