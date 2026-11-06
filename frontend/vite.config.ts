import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite forwards API calls to FastAPI.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', "");
  const backend =
    env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000";

  const apiPrefixes = [
    "/auth",
    "/admin",
    "/reference",
    "/scans",
    "/health",
  ];

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: Object.fromEntries(
        apiPrefixes.map((prefix) => [
          prefix,
          { target: backend, changeOrigin: true },
        ]),
      ),
    },
  };
});
