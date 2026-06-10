export interface NavItemDefinition {
  readonly id: string;
  readonly title: string;
  readonly href: string;
  /** When set, the sidebar shows a heading when the group changes (matches frontend workspace nav). */
  readonly groupTitle?: string;
}
