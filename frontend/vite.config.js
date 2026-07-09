import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In docker-compose this points at the "backend" service name; locally it
// defaults to localhost.
const apiTarget = process.env.API_PROXY_TARGET || "http://localhost:8000";
const wsTarget = apiTarget.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": apiTarget,
      "/ws": { target: wsTarget, ws: true },
    },
  },
});
