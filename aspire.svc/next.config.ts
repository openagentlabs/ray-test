import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.join(configDir, "..");

const nextConfig: NextConfig = {
  /** Resolve `file:../iam.svc/client` and other workspace siblings from `aspire.svc/`. */
  outputFileTracingRoot: monorepoRoot,
  experimental: {
    externalDir: true,
  },
  serverExternalPackages: [
    "better-sqlite3",
    "@grpc/grpc-js",
    "@bufbuild/protobuf",
  ],
};

export default nextConfig;
