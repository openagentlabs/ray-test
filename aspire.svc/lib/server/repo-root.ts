import "server-only";

import path from "node:path";

/**
 * Repository root (parent of the `aspire.svc/` app) for resolving `workdir_relative` rows.
 */
export function resolveRepoRoot(): string {
  const override = process.env.ARB_REPO_ROOT?.trim();
  if (override !== undefined && override.length > 0) {
    return path.resolve(override);
  }
  return path.resolve(process.cwd(), "..");
}

/**
 * Root of the Aspire Next.js app (where `service-registry.sqlite` and `.aspire/` live).
 */
export function resolveAspireRoot(): string {
  return path.resolve(process.cwd());
}
