import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@arb/http-auth-client"],
  turbopack: {
    root: path.join(__dirname, ".."),
  },
};

export default nextConfig;
