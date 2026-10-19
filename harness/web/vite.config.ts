import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const runtimeUrl = process.env.RUNTIME_URL ?? "http://127.0.0.1:8101";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/copilotkit": { target: runtimeUrl, changeOrigin: true },
      "/api": { target: runtimeUrl, changeOrigin: true },
    },
  },
});
