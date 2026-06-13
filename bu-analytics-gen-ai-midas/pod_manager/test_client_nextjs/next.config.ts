import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

/** Repo root — Turbopack must resolve `file:../router.svc/client_ts` outside the Next app dir. */
const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

const nextConfig: NextConfig = {
  transpilePackages: ["@router/client-ts"],
  serverExternalPackages: ["@grpc/grpc-js"],
  turbopack: {
    root: repoRoot,
  },
};

export default nextConfig;
