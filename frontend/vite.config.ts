import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into the Python package so FastAPI serves it at /app.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "../src/regintel/api/webapp",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Keep the chart library in its own long-lived cacheable chunk.
        manualChunks: { charts: ["recharts"], react: ["react", "react-dom", "react-router-dom"] },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
