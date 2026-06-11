import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend runs on :8000. Proxy API paths so the browser can use
// same-origin relative URLs in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      [
        "/account",
        "/auth",
        "/conversation",
        "/lesson",
        "/grammar",
        "/leaderboard",
        "/word",
        "/words",
        "/vocab",
        "/profiler",
        "/profile",
        "/produce",
        "/session",
        "/settings",
        "/progress",
        "/transcribe",
        "/translate",
        "/tts",
        "/health",
      ].map((p) => [p, { target: "http://localhost:8000", changeOrigin: true }])
    ),
  },
});
