import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";

// Charge .env.local AVANT de lire process.env.PI_URL
loadEnvConfig(process.cwd());

const PI_URL = process.env.PI_URL || "http://192.168.1.191:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/stats", destination: `${PI_URL}/stats` },
      { source: "/api/identities", destination: `${PI_URL}/identities` },
      {
        source: "/api/identities/:id",
        destination: `${PI_URL}/identities/:id`,
      },
      { source: "/api/logs", destination: `${PI_URL}/logs` },
      { source: "/api/enroll", destination: `${PI_URL}/enroll` },
      { source: "/api/verify", destination: `${PI_URL}/verify` },
      { source: "/api/health", destination: `${PI_URL}/health` },
      {
        source: "/api/stream/:path*",
        destination: `${PI_URL}/stream/:path*`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${PI_URL}/admin/:path*`,
      },
    ];
  },
};

export default nextConfig;
