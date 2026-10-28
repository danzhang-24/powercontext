/**
 * 文档切片:把导入的长文本切成适合 embedding 的小块
 */

export interface Chunk {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
}

const DEFAULT_MAX_CHARS = 420;
const DEFAULT_OVERLAP = 60;

/** 按句号/问号/感叹号/换行切句 */
function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[。！？!?\.\n])/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * 切片:优先按段落聚合,超长段落再按句子切
 */
export function chunkDocument(
  text: string,
  meta: Record<string, unknown> = {},
  opts: { maxChars?: number; overlap?: number; idPrefix?: string } = {},
): Chunk[] {
  const maxChars = opts.maxChars ?? DEFAULT_MAX_CHARS;
  const overlap = opts.overlap ?? DEFAULT_OVERLAP;
  const prefix = opts.idPrefix ?? "doc";

  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  const chunks: string[] = [];
  let buf = "";

  const pushBuf = () => {
    if (buf.trim()) chunks.push(buf.trim());
    buf = "";
  };

  for (const para of paragraphs) {
    if (para.length > maxChars) {
      pushBuf();
      let sBuf = "";
      for (const sent of splitSentences(para)) {
        if ((sBuf + sent).length > maxChars && sBuf) {
          chunks.push(sBuf.trim());
          sBuf = sBuf.slice(Math.max(0, sBuf.length - overlap)) + sent;
        } else {
          sBuf += sent;
        }
      }
      if (sBuf.trim()) chunks.push(sBuf.trim());
      continue;
    }
    if ((buf + "\n\n" + para).length > maxChars) {
      pushBuf();
      // 相邻块保留一点重叠,避免语义在边界被切断
      if (buf.length > overlap) {
        buf = buf.slice(buf.length - overlap);
      }
    }
    buf += (buf ? "\n\n" : "") + para;
  }
  pushBuf();

  return chunks.map((c, i) => ({
    id: `${prefix}-${i}`,
    text: c,
    metadata: { ...meta, chunk: i, chars: c.length },
  }));
}

/** 生成稳定 id(同一份内容重复导入不会产生冲突) */
export function stableId(prefix: string, text: string): string {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return `${prefix}-${(h >>> 0).toString(36)}`;
}
