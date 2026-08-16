import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const conductorServerUrl = env.VITE_CONDUCTOR_SERVER_URL || "http://localhost:8080";

  return {
    plugins: [react()],
    server: {
      // Proxies browser calls to the Conductor server so the UI can call its
      // REST API directly (no API server of our own) without hitting CORS —
      // Conductor's server has no CORS config and 403s cross-origin requests.
      proxy: {
        "/api": {
          target: conductorServerUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
