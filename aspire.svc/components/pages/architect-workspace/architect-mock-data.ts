export const ARCHITECT_WORKSPACE_TABS = [
  "Calendar",
  "Case Roster",
  "Program Enrollment",
  "Search",
  "Tasks",
  "Tracker",
] as const;

export type ArchitectWorkspaceTab = (typeof ARCHITECT_WORKSPACE_TABS)[number];

export const PROGRAM_TYPEAHEAD_OPTIONS: readonly string[] = Object.freeze([
  "Care Management",
  "Transitional Care",
  "Behavioral Health",
  "Chronic Disease",
  "Maternal Health",
  "Pediatric Care",
]);
