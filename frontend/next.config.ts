import type { NextConfig } from "next";

// The QATRA engine API (ai_engine: `uv run uvicorn qatra_ai.service.app:app --port 8100`).
// Server-side only; the browser always calls same-origin /api/*.
const ENGINE_API_URL = process.env.ENGINE_API_URL ?? "http://localhost:8100";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${ENGINE_API_URL}/api/:path*` }];
  },
};

export default nextConfig;
