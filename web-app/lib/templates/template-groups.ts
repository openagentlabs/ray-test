export const TEMPLATES_INDEX_PATH = "/pages/templates";

export interface TemplateGroupDefinition {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly href: string;
  readonly componentCount: number;
}

export const TEMPLATE_GROUPS: readonly TemplateGroupDefinition[] = Object.freeze([
  {
    id: "buttons",
    title: "Buttons",
    description:
      "Primary, secondary, outline, ghost, destructive, and link actions with size and state variants.",
    href: "/pages/templates/buttons",
    componentCount: 1,
  },
  {
    id: "forms",
    title: "Form controls",
    description:
      "Inputs, labels, checkboxes, switches, and text areas with validation and disabled states.",
    href: "/pages/templates/forms",
    componentCount: 5,
  },
  {
    id: "feedback",
    title: "Feedback",
    description: "Alerts and badges for status, validation, and contextual emphasis.",
    href: "/pages/templates/feedback",
    componentCount: 2,
  },
  {
    id: "navigation",
    title: "Navigation",
    description: "Tabs and dropdown menus for section switching and compact actions.",
    href: "/pages/templates/navigation",
    componentCount: 2,
  },
  {
    id: "layout",
    title: "Layout & surfaces",
    description: "Cards, separators, collapsibles, and scroll regions for structured content.",
    href: "/pages/templates/layout",
    componentCount: 4,
  },
  {
    id: "data-display",
    title: "Data display",
    description: "Avatars and tooltips for identity chips and contextual hints.",
    href: "/pages/templates/data-display",
    componentCount: 2,
  },
] satisfies TemplateGroupDefinition[]);
