/**
 * Values safe to import from client components.
 * Display name matches `PRJ_NAME` in `.cursor/rules/constants.mdc`.
 */
export class AppPublicConfig {
  public static readonly applicationName = "ARB - AI Assistant";

  public static readonly sidebarStorageKey = "manager_web.sidebar.collapsed";

  public static readonly themeStorageKey = "manager_web.theme";

  private constructor() {}
}
