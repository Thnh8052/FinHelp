import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Only in the built site: the development server injects inline scripts of its own. Limits what a script slipped into the page could load or send.
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com", // data: the build inlines the small KaTeX fonts
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

// The backend the development server forwards /api to; another one (a second backend on another port) via VITE_API_TARGET
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "content-security-policy",
      apply: "build",
      transformIndexHtml: () => [
        { tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CONTENT_SECURITY_POLICY }, injectTo: "head-prepend" },
      ],
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
      "/health": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
});
