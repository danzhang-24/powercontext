/**
 * 查询关键词抽取(中文/英文)
 *
 * 关键词只用于 seekdb 的「全文检索分支」;向量分支用的是浏览器端算出的查询向量。
 * 两路结果由 seekdb 内部 RRF 融合,前端不做任何自行拼合。
 */

const STOPWORDS = new Set([
  "的", "了", "和", "是", "在", "我", "有", "就", "不", "人", "都", "一", "一个", "上", "也",
  "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "吗",
  "什么", "怎么", "如何", "为什么", "哪些", "哪个", "可以", "需要", "使用", "进行", "以及",
  "the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "on", "with", "how",
  "what", "why", "which", "can", "does", "do", "i", "my", "it", "this", "that", "be", "use",
]);

const CJK = /[\u4e00-\u9fa5\u3400-\u4dbf]/;

/** 高频虚词/语气词:出现在词块首尾时说明它切到了无意义的片段,直接丢掉 */
const NOISE_CHARS = new Set([
  "的", "了", "是", "在", "和", "就", "不", "都", "很", "也", "有", "我", "你", "他", "她", "它",
  "这", "那", "个", "们", "吗", "呢", "吧", "啊", "把", "被", "给", "让", "对", "从", "到", "要",
  "会", "能", "可", "以", "上", "下", "中", "为", "之", "其", "所", "如", "何", "么", "什",
  "怎", "样", "哪", "谁", "请", "帮", "想", "要", "做", "去", "来", "说", "看", "用", "有",
]);

/** 把一段文本切成候选词:英文按单词,中文按二元组(bigram) */
function tokenize(text: string): string[] {
  const tokens: string[] = [];
  const normalized = text.toLowerCase();

  // 英文/数字词
  for (const m of normalized.matchAll(/[a-z][a-z0-9_+#.-]{1,}/g)) {
    tokens.push(m[0].replace(/[.\-_]+$/, ""));
  }

  // 中文连续片段 -> 二元组(bigram) + 三元组(trigram)
  for (const m of normalized.matchAll(/[\u4e00-\u9fa5\u3400-\u4dbf]+/g)) {
    const seg = m[0];
    if (seg.length === 1) {
      tokens.push(seg);
      continue;
    }
    for (let i = 0; i < seg.length - 1; i++) {
      const bg = seg.slice(i, i + 2);
      // 首尾都是虚词的片段没有检索价值
      if (NOISE_CHARS.has(bg[0]) || NOISE_CHARS.has(bg[1])) continue;
      tokens.push(bg);
    }
    // 长度 >=3 的片段同时保留三元组,提升专有词命中率
    if (seg.length >= 3) {
      for (let i = 0; i < seg.length - 2; i++) {
        const tg = seg.slice(i, i + 3);
        if (NOISE_CHARS.has(tg[0]) || NOISE_CHARS.has(tg[2])) continue;
        tokens.push(tg);
      }
    }
  }
  return tokens;
}

/**
 * 抽取关键词,返回给 seekdb 全文检索分支使用
 */
export function extractKeywords(query: string, max = 10): string[] {
  const raw = tokenize(query);
  const freq = new Map<string, number>();

  for (const t of raw) {
    if (t.length < 2) continue;
    if (STOPWORDS.has(t)) continue;
    freq.set(t, (freq.get(t) ?? 0) + 1);
  }

  // 去掉被更长词包含的短词(例如已有「向量检」就不再单独保留「向量」)
  const sorted = [...freq.keys()].sort((a, b) => b.length - a.length || (freq.get(b) ?? 0) - (freq.get(a) ?? 0));
  const picked: string[] = [];
  for (const t of sorted) {
    if (picked.length >= max) break;
    if (picked.some((p) => p.includes(t))) continue;
    picked.push(t);
  }
  return picked;
}

/** 判断一段文本是否包含中文,用于选择分词粒度 */
export function hasCJK(text: string): boolean {
  return CJK.test(text);
}
