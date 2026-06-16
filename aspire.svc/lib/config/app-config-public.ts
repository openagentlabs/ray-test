/**
 * Values safe to import from client components.
 * Display name matches `PRJ_NAME` in `.cursor/rules/constants/constants.mdc`.
 */
export class AppPublicConfig {
  public static readonly applicationName = "AI Smart Assistant";

  public static readonly sidebarStorageKey = "arb_sherpa.sidebar.collapsed";

  public static readonly themeStorageKey = "arb_sherpa.theme";

  private constructor() {}
}
