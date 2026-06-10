/**
 * Architect workspace data gateway — **MOCK** implementation.
 *
 * ---------------------------------------------------------------------------
 * Replace this module’s `fetchArchitectWorkspaceData` with a server-side gRPC
 * client via `@arb/*-service-client`. Expose data through server actions or
 * same-origin `/app/api/*` routes — never call gRPC from client components.
 *
 * Request / response types live in `@/lib/types/architect-workspace` and should
 * map from protobuf or validated DTOs at the server boundary.
 * ---------------------------------------------------------------------------
 */

import { sortArchitectRosterRows } from "@/lib/architect/architect-roster-sort";
import { ARCHITECT_ROSTER_SEED_ROWS } from "@/lib/architect/architect-workspace-seed";
import type {
  ArchitectRosterFiltersPayload,
  ArchitectRosterRow,
  ArchitectSolutionSummaryCounts,
  ArchitectWorkspaceDataRequest,
  ArchitectWorkspaceDataResponse,
} from "@/lib/types/architect-workspace";

/** Stable mock identity — substitute with session `sub` / internal user id. */
export const ARCHITECT_WORKSPACE_MOCK_USER_ID = "usr_mock_architect_001";

/** Simulated network delay (ms). Increase briefly to exercise loading UI. */
const MOCK_NETWORK_DELAY_MS = 0;

let mockArchitectRosterStore: ArchitectRosterRow[] = [...ARCHITECT_ROSTER_SEED_ROWS];

export function resetArchitectWorkspaceMockStore(): void {
  mockArchitectRosterStore = [...ARCHITECT_ROSTER_SEED_ROWS];
}

export function deleteArchitectWorkspaceMockRows(ids: ReadonlySet<string>): void {
  mockArchitectRosterStore = mockArchitectRosterStore.filter((r) => !ids.has(r.id));
}

export function insertArchitectWorkspaceMockRow(row: ArchitectRosterRow): void {
  mockArchitectRosterStore = [row, ...mockArchitectRosterStore];
}

function rowMatchesFilters(row: ArchitectRosterRow, f: ArchitectRosterFiltersPayload): boolean {
  const q = f.keyword.trim().toLowerCase();
  const matchesKeyword =
    q.length === 0 ||
    row.memberName.toLowerCase().includes(q) ||
    row.caseId.toLowerCase().includes(q);

  const matchesDialogProgram =
    f.dialogProgramExact.trim().length === 0 ||
    row.program.toLowerCase() === f.dialogProgramExact.trim().toLowerCase();

  const matchesDialogStatus =
    f.dialogStatusExact.trim().length === 0 ||
    row.status.toLowerCase() === f.dialogStatusExact.trim().toLowerCase();

  const matchesChips =
    f.statusChipAllowlist.length === 0 ||
    f.statusChipAllowlist.some((m) => m.toLowerCase() === row.status.toLowerCase());

  const matchesProgramExact =
    f.programExact.trim().length === 0 ||
    row.program.toLowerCase() === f.programExact.trim().toLowerCase();

  return (
    matchesKeyword &&
    matchesDialogProgram &&
    matchesDialogStatus &&
    matchesChips &&
    matchesProgramExact
  );
}

function applyArchitectRosterFilters(
  rows: readonly ArchitectRosterRow[],
  filters: ArchitectRosterFiltersPayload,
): ArchitectRosterRow[] {
  return rows.filter((r) => rowMatchesFilters(r, filters));
}

/**
 * Summary metrics derived from the **filtered** roster slice (same rules as a
 * dedicated aggregate endpoint could use server-side).
 */
export function computeArchitectSolutionSummary(
  filteredRows: readonly ArchitectRosterRow[],
): ArchitectSolutionSummaryCounts {
  const atRiskStatuses = new Set(["Pending", "On hold"]);
  let atRisk = 0;
  let onTrack = 0;
  let completed = 0;
  for (const row of filteredRows) {
    if (row.status === "Active") {
      onTrack += 1;
    } else if (row.status === "Closed") {
      completed += 1;
    } else if (atRiskStatuses.has(row.status)) {
      atRisk += 1;
    }
  }
  return Object.freeze({
    assignedToArchitect: filteredRows.length,
    atRisk,
    onTrack,
    completed,
  });
}

async function delayMockNetwork(): Promise<void> {
  if (MOCK_NETWORK_DELAY_MS > 0) {
    await new Promise<void>((resolve) => {
      setTimeout(resolve, MOCK_NETWORK_DELAY_MS);
    });
  }
}

/**
 * Single entry point for workspace reads. Swap this body for your microservice.
 */
export async function fetchArchitectWorkspaceData(
  request: ArchitectWorkspaceDataRequest,
): Promise<ArchitectWorkspaceDataResponse> {
  await delayMockNetwork();

  const filtered = applyArchitectRosterFilters(mockArchitectRosterStore, request.filters);
  const summary = computeArchitectSolutionSummary(filtered);
  const rows = sortArchitectRosterRows(filtered, request.sort);

  return {
    rows,
    summary,
  };
}
