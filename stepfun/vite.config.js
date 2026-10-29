import { defineConfig } from "vite";

export default defineConfig({
  root: "web",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // 本地开发时把 API 转发到 Node server(seekdb 数据层)
      "/api": { target: "http://127.0.0.1:8787", changeOrigin: true },
    },
  },
  optimizeDeps: {
    exclude: ["@huggingface/transformers"],
  },
});
