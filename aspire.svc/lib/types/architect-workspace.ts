/**
 * Serializable types for the architect workspace UI and its backing services.
 * Keep these JSON-friendly so they can cross a future microservice boundary unchanged.
 */

export type ArchitectRosterSortKey =
  | "caseId"
  | "memberName"
  | "program"
  | "status"
  | "nextReview";

export interface ArchitectRosterRow {
  readonly id: string;
  readonly caseId: string;
  readonly memberName: string;
  readonly program: string;
  readonly status: string;
  readonly nextReview: string;
  readonly detailNote: string;
}

export interface ArchitectRosterSortEntry {
  readonly column: ArchitectRosterSortKey;
  readonly direction: "asc" | "desc";
}

/** Summary strip metrics — typically returned alongside roster or from a dedicated aggregate endpoint. */
export interface ArchitectSolutionSummaryCounts {
  readonly assignedToArchitect: number;
  readonly atRisk: number;
  readonly onTrack: number;
  readonly completed: number;
}

/** IAM-backed people counts for the architect workspace summary strip (mapped from `GetUserTypeStats`). */
export interface ArchitectIamRoleSummaryCounts {
  readonly admins: number;
  readonly solutionOwners: number;
  readonly architects: number;
  readonly softwareDevs: number;
  readonly devops: number;
}

/** Who is asking (maps to JWT / session claims in production). */
export interface ArchitectWorkspaceContext {
  readonly userId: string;
  /** Optional partition for multi-tenant routing, e.g. org or realm id. */
  readonly tenantId?: string;
}

/**
 * Roster filter payload — mirrors what a microservice query would accept.
 * All fields are optional strings / arrays; empty string or empty array means "no constraint".
 */
export interface ArchitectRosterFiltersPayload {
  /** Case-insensitive substring match on member name and case id. */
  readonly keyword: string;
  /** Exact program match from the table filter dialog (mock). */
  readonly dialogProgramExact: string;
  /** Exact status match from the table filter dialog (mock). */
  readonly dialogStatusExact: string;
  /** When non-empty, row.status must match one of these (advanced multi-select). */
  readonly statusChipAllowlist: readonly string[];
  /** When non-empty, row.program must equal this (program picker / type-ahead selection). */
  readonly programExact: string;
}

/**
 * Single round-trip shape for a future `POST /architect/workspace/query`-style endpoint.
 * Replace the mock client implementation with fetch() using this JSON body.
 */
export interface ArchitectWorkspaceDataRequest {
  readonly context: ArchitectWorkspaceContext;
  readonly filters: ArchitectRosterFiltersPayload;
  readonly sort: readonly ArchitectRosterSortEntry[];
}

export interface ArchitectWorkspaceDataResponse {
  readonly rows: readonly ArchitectRosterRow[];
  readonly summary: ArchitectSolutionSummaryCounts;
}
