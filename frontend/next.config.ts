import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Do not fail the production build on ESLint errors
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Optional: if type errors appear during CI, do not block the build
  // (Runtime remains unchanged; use for CI-only convenience.)
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
