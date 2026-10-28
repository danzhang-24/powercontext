/**
 * 端侧 embedding 引擎
 *
 * - 运行时:Transformers.js(v4) + ONNX Runtime Web
 * - 后端优先级:WebGPU -> WASM(自动降级,界面显式提示)
 * - 精度:fp32(基线) / fp16 / q8(INT8)
 *
 * 所有推理都发生在用户设备的浏览器里,只调用模型文件,不调用任何云端推理 API。
 */
import { pipeline, env, type FeatureExtractionPipeline } from "@huggingface/transformers";

export const MODEL_ID = "Xenova/all-MiniLM-L6-v2";

/** 三种精度对应的 onnx 权重文件(与 scripts/fetch_model.mjs 下载的一致) */
export const DTYPE_FILES: Record<Dtype, string> = {
  fp32: "model.onnx",
  fp16: "model_fp16.onnx",
  q8: "model_quantized.onnx",
};

export type Dtype = "fp32" | "fp16" | "q8";
export type Backend = "webgpu" | "wasm";

env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = "/models/";
const wasmBackend = env.backends.onnx.wasm!;
wasmBackend.wasmPaths = "/ort/";
// 未开启跨源隔离(COOP/COEP)时不能用多线程 SharedArrayBuffer,退化为单线程
wasmBackend.numThreads = (globalThis as any).crossOriginIsolated
  ? Math.min(4, navigator.hardwareConcurrency || 1)
  : 1;

export interface LoadInfo {
  backend: Backend;
  dtype: Dtype;
  loadMs: number;
  /** 模型权重文件下载耗时(与「加载」分开统计) */
  downloadMs: number;
  modelBytes: number;
  fellBack: boolean;
  reason?: string;
  /** WebGPU adapter 信息(vendor/architecture/description),WebGPU 不可用时为 null */
  adapter?: { vendor?: string; architecture?: string; description?: string } | null;
}

export class Embedder {
  private pipe: FeatureExtractionPipeline | null = null;
  private info: LoadInfo | null = null;

  get loaded() {
    return this.pipe !== null;
  }
  get current() {
    return this.info;
  }

  /** 探测 WebGPU 是否真的可用(有 adapter 才算可用) */
  static async webgpuAvailable(): Promise<boolean> {
    return !!(await Embedder.webgpuAdapter());
  }

  /** 取 WebGPU adapter(拿不到就是不可用) */
  static async webgpuAdapter(): Promise<any> {
    const gpu = (navigator as any).gpu;
    if (!gpu) return null;
    try {
      return (await gpu.requestAdapter()) ?? null;
    } catch {
      return null;
    }
  }

  /** adapter 的可读信息(vendor/architecture/description) */
  static async adapterInfo(): Promise<LoadInfo["adapter"]> {
    const adapter = await Embedder.webgpuAdapter();
    if (!adapter) return null;
    const info = (adapter as any).info ?? {};
    return {
      vendor: info.vendor ?? undefined,
      architecture: info.architecture ?? undefined,
      description: info.description ?? undefined,
    };
  }

  /**
   * 加载模型。preferWebGPU 为 true 且环境支持时走 WebGPU,
   * 建 session 失败时自动降级到 WASM,并记录降级原因。
   */
  async load(dtype: Dtype, preferWebGPU = true): Promise<LoadInfo> {
    const t0 = performance.now();
    const adapter = preferWebGPU ? await Embedder.webgpuAdapter() : null;
    const wantWebGPU = !!adapter;
    let fellBack = false;
    let reason: string | undefined;

    const build = async (device: Backend) =>
      pipeline("feature-extraction", MODEL_ID, {
        device,
        dtype,
        progress_callback: undefined,
      } as any);

    // 后端以「实际建成的 session 使用的 device」为准:
    // transformers.js 把 device 映射成 onnxruntime 的 execution provider,
    // 建 session 失败(例如 adapter 不支持 fp16)会抛错,此时退回 WASM。
    let backend: Backend = wantWebGPU ? "webgpu" : "wasm";
    try {
      this.pipe = await build(backend);
    } catch (e) {
      if (backend === "webgpu") {
        fellBack = true;
        reason = `WebGPU 初始化失败(${(e as Error).message}),已自动降级到 WASM`;
        backend = "wasm";
        this.pipe = await build("wasm");
      } else {
        throw e;
      }
    }
    if (!wantWebGPU && preferWebGPU) {
      fellBack = true;
      reason = "当前浏览器/设备没有可用的 WebGPU adapter,已自动降级到 WASM";
    }

    const loadMs = performance.now() - t0;
    const modelBytes = await this.probeModelSize(dtype);
    const downloadMs = this.probeDownloadTime(dtype);

    this.info = {
      backend,
      dtype,
      loadMs,
      downloadMs,
      modelBytes,
      fellBack,
      reason,
      adapter: backend === "webgpu" ? await Embedder.adapterInfo() : null,
    };
    return this.info;
  }

  /**
   * 从 Performance Resource Timing 里取模型权重文件的下载耗时。
   * 浏览器会缓存权重,这里取的是本次页面会话里最后一次加载该文件的记录。
   */
  private probeDownloadTime(dtype: Dtype): number {
    try {
      const file = DTYPE_FILES[dtype];
      const entries = performance
        .getEntriesByType("resource")
        .filter((e) => (e as PerformanceResourceTiming).name.includes(file)) as PerformanceResourceTiming[];
      if (!entries.length) return 0;
      const last = entries[entries.length - 1];
      return last.duration ?? 0;
    } catch {
      return 0;
    }
  }

  /** 读取本地模型文件大小,用于报告量化前后体积与压缩比 */
  private async probeModelSize(dtype: Dtype): Promise<number> {
    try {
      const url = `/models/${MODEL_ID}/onnx/${DTYPE_FILES[dtype]}`;
      const res = await fetch(url, { method: "HEAD" });
      const len = res.headers.get("content-length");
      if (len) return Number(len);
    } catch {
      /* ignore */
    }
    return 0;
  }

  /**
   * 批量向量化(浏览器本地推理)
   * @returns number[][] 每条文本一个 384 维向量
   */
  async embed(texts: string[], batchSize = 16): Promise<number[][]> {
    if (!this.pipe) throw new Error("模型尚未加载");
    const out: number[][] = [];

    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize);
      const tensor = await this.pipe(batch, { pooling: "mean", normalize: true } as any);
      const data = tensor.data as Float32Array | number[];
      const dims = tensor.dims as number[];
      const dim = dims[dims.length - 1];
      const rows = dims.length > 1 ? dims[0] : batch.length;

      for (let r = 0; r < rows; r++) {
        const row = new Array<number>(dim);
        for (let c = 0; c < dim; c++) row[c] = Number(data[r * dim + c]);
        out.push(row);
      }
    }
    return out;
  }

  /** 单条查询向量化 */
  async embedQuery(text: string): Promise<number[]> {
    const [v] = await this.embed([text]);
    return v;
  }
}
