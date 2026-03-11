import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const apiProxyTarget =
  process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";
const wsProxyTarget =
  process.env.VITE_WS_PROXY_TARGET ??
  apiProxyTarget.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api/v1": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: wsProxyTarget,
        ws: true,
      },
      "/tv": {
        target: "https://charting-library.tradingview-widget.com",
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/tv/, ""),
      },
    },
  },
});
