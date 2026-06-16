import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";

/**
 * Values safe to import from client components.
 */
export class AppPublicConfig {
  public static readonly applicationName = DECISION_AI_NAME;

  public static readonly sidebarStorageKey = "manager_web.sidebar.collapsed";

  public static readonly themeStorageKey = "manager_web.theme";

  private constructor() {}
}
