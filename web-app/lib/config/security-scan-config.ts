/**
 * Security scan output paths for manager-web production / full builds.
 * Scan logs are written under `<projectRoot>/<projectFolderName>/`.
 */
export class SecurityScanConfig {
  public static readonly projectFolderName = "manager-web";

  public static readonly scanLogRootRelative = SecurityScanConfig.projectFolderName;

  public static readonly skipScanEnvVar = "MANAGER_WEB_SKIP_SECURITY_SCAN";

  public static readonly tools = Object.freeze([
    {
      id: "syft",
      name: "Syft",
      vendor: "Anchore",
      purpose: "Software Bill of Materials (SBOM) extraction",
    },
    {
      id: "grype",
      name: "Grype",
      vendor: "Anchore",
      purpose: "High-speed vulnerability matching",
    },
    {
      id: "trivy",
      name: "Trivy",
      vendor: "Aqua Security",
      purpose: "Vulnerability, configuration, and secret scanning",
    },
  ] as const);

  private constructor() {}
}
