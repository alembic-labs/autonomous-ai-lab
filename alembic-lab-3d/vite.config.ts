import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Default backend the dev/preview servers proxy /api/* requests to.
// Override with VITE_BACKEND_ORIGIN if pointing at a local backend.
const BACKEND_ORIGIN =
  process.env.VITE_BACKEND_ORIGIN || "https://api.alembic.bio";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    proxy: {
      // Forward /api/* to the live backend so the 3D lab can read live
      // agent statuses from the same FastAPI service the main site uses,
      // without tripping CORS in development.
      "/api": {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
        secure: true,
      },
    },
  },
  preview: {
    port: 4173,
    strictPort: true,
    host: true,
    proxy: {
      "/api": {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
        secure: true,
      },
    },
  },
  build: { chunkSizeWarningLimit: 12000 },
});
