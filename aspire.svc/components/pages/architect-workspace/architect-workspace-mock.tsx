"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import {
  deleteArchitectWorkspaceMockRows,
  fetchArchitectWorkspaceData,
  insertArchitectWorkspaceMockRow,
  resetArchitectWorkspaceMockStore,
  ARCHITECT_WORKSPACE_MOCK_USER_ID,
} from "@/lib/architect/architect-workspace-api";
import type { ArchitectWorkspaceDataRequest } from "@/lib/types/architect-workspace";
import type { RegisteredServicesLoadResult } from "@/lib/types/registered-services-load-result";

import {
  ARCHITECT_WORKSPACE_TABS,
  PROGRAM_TYPEAHEAD_OPTIONS,
  type ArchitectWorkspaceTab,
} from "./architect-mock-data";
import type {
  ArchitectIamRoleSummaryCounts,
  ArchitectRosterRow,
  ArchitectRosterSortEntry,
  ArchitectRosterSortKey,
  ArchitectSolutionSummaryCounts,
} from "./architect-types";
import { ArchitectRosterFiltersPanel } from "./components/architect-roster-filters-panel";
import { ArchitectRosterTablePanel } from "./components/architect-roster-table-panel";
import { IamRoleSummaryPanels } from "./components/iam-role-summary-panels";
import { RegisteredServicesPanel } from "./components/registered-services-panel";
import { ArchitectWorkspaceChrome } from "./components/architect-workspace-chrome";
import { ArchitectWorkspaceDialogs } from "./components/architect-workspace-dialogs";
import { SolutionSummaryPanels } from "./components/solution-summary-panels";

const EMPTY_SUMMARY: ArchitectSolutionSummaryCounts = Object.freeze({
  assignedToArchitect: 0,
  atRisk: 0,
  onTrack: 0,
  completed: 0,
});

const EMPTY_ROLE_COUNTS: ArchitectIamRoleSummaryCounts = Object.freeze({
  admins: 0,
  solutionOwners: 0,
  architects: 0,
  softwareDevs: 0,
  devops: 0,
});

export function ArchitectWorkspaceMock({
  registeredServicesBootstrap,
}: {
  readonly registeredServicesBootstrap: RegisteredServicesLoadResult;
}) {
  const [activeTab, setActiveTab] = useState<ArchitectWorkspaceTab>("Case Roster");
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [sorts, setSorts] = useState<readonly ArchitectRosterSortEntry[]>([
    { column: "nextReview", direction: "asc" },
  ]);
  const [expandedId, setExpandedId] = useState<string | undefined>(undefined);
  const [keyword, setKeyword] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [addTabOpen, setAddTabOpen] = useState(false);
  const [lookupOpen, setLookupOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [filterDraft, setFilterDraft] = useState({ program: "", status: "" });
  const [appliedFilter, setAppliedFilter] = useState({ program: "", status: "" });
  const [typeaheadQuery, setTypeaheadQuery] = useState("");
  const [programFilter, setProgramFilter] = useState("");
  const [multiSelected, setMultiSelected] = useState<readonly string[]>([]);
  const [multiQuery, setMultiQuery] = useState("");
  const selectAllRef = useRef<HTMLInputElement>(null);

  const [rosterRows, setRosterRows] = useState<readonly ArchitectRosterRow[]>([]);
  const [summary, setSummary] =
    useState<ArchitectSolutionSummaryCounts>(EMPTY_SUMMARY);
  const [roleCounts, setRoleCounts] =
    useState<ArchitectIamRoleSummaryCounts>(EMPTY_ROLE_COUNTS);
  const [iamStatsError, setIamStatsError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const [iamStatsVersion, setIamStatsVersion] = useState(0);
  const [workspacePending, startWorkspaceTransition] = useTransition();

  const dataRequest = useMemo(
    (): ArchitectWorkspaceDataRequest => ({
      context: {
        userId: ARCHITECT_WORKSPACE_MOCK_USER_ID,
        tenantId: undefined,
      },
      filters: {
        keyword,
        dialogProgramExact: appliedFilter.program,
        dialogStatusExact: appliedFilter.status,
        statusChipAllowlist: multiSelected,
        programExact: programFilter,
      },
      sort: sorts,
    }),
    [
      appliedFilter.program,
      appliedFilter.status,
      keyword,
      multiSelected,
      programFilter,
      sorts,
    ],
  );

  useEffect(() => {
    let cancelled = false;
    startWorkspaceTransition(() => {
      void fetchArchitectWorkspaceData(dataRequest)
        .then((response) => {
          if (cancelled) {
            return;
          }
          setWorkspaceError(null);
          setRosterRows(response.rows);
          setSummary(response.summary);
          setSelectedIds((prev) => {
            const next = new Set<string>();
            for (const id of prev) {
              if (response.rows.some((r) => r.id === id)) {
                next.add(id);
              }
            }
            return next;
          });
        })
        .catch((err: unknown) => {
          if (cancelled) {
            return;
          }
          const message =
            err instanceof Error ? err.message : "Workspace request failed.";
          setWorkspaceError(message);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [dataRequest, dataVersion]);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/iam/user-type-stats")
      .then(async (res) => {
        const raw: unknown = await res.json();
        if (cancelled) {
          return;
        }
        if (!res.ok || raw === null || typeof raw !== "object") {
          const message =
            raw !== null &&
            typeof raw === "object" &&
            "error" in raw &&
            typeof (raw as { error?: unknown }).error === "string"
              ? (raw as { error: string }).error
              : `IAM stats request failed (${res.status}).`;
          setIamStatsError(message);
          setRoleCounts(EMPTY_ROLE_COUNTS);
          return;
        }
        const body = raw as { roles?: ArchitectIamRoleSummaryCounts };
        if (!body.roles) {
          setIamStatsError("IAM stats response was missing role counts.");
          setRoleCounts(EMPTY_ROLE_COUNTS);
          return;
        }
        setIamStatsError(null);
        setRoleCounts(body.roles);
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setIamStatsError(err instanceof Error ? err.message : "IAM stats request failed.");
        setRoleCounts(EMPTY_ROLE_COUNTS);
      });
    return () => {
      cancelled = true;
    };
  }, [iamStatsVersion]);

  const visibleIds = useMemo(() => rosterRows.map((r) => r.id), [rosterRows]);
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const someVisibleSelected = visibleIds.some((id) => selectedIds.has(id));

  const typeaheadMatches = useMemo(() => {
    const q = typeaheadQuery.trim().toLowerCase();
    return PROGRAM_TYPEAHEAD_OPTIONS.filter((o) => o.toLowerCase().includes(q));
  }, [typeaheadQuery]);

  const statusOptions = useMemo(
    () => ["Active", "Pending", "On hold", "Closed"] as const,
    [],
  );
  const multiPool = useMemo(() => {
    const q = multiQuery.trim().toLowerCase();
    return statusOptions.filter(
      (s) =>
        s.toLowerCase().includes(q) &&
        !multiSelected.some((m) => m.toLowerCase() === s.toLowerCase()),
    );
  }, [multiQuery, multiSelected, statusOptions]);

  const handleSort = useCallback((column: ArchitectRosterSortKey) => {
    setSorts((prev) => {
      const idx = prev.findIndex((s) => s.column === column);
      if (idx >= 0) {
        const cur = prev[idx]!;
        const flipped: ArchitectRosterSortEntry = {
          column,
          direction: cur.direction === "asc" ? "desc" : "asc",
        };
        const rest = prev.filter((_, i) => i !== idx);
        return [flipped, ...rest];
      }
      return [{ column, direction: "asc" }, ...prev];
    });
  }, []);

  const toggleRow = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedIds((prev) => {
      if (allVisibleSelected) {
        const next = new Set(prev);
        for (const id of visibleIds) {
          next.delete(id);
        }
        return next;
      }
      const next = new Set(prev);
      for (const id of visibleIds) {
        next.add(id);
      }
      return next;
    });
  }, [allVisibleSelected, visibleIds]);

  const bumpDataVersion = useCallback(() => {
    setDataVersion((v) => v + 1);
  }, []);

  const deleteSelected = useCallback(() => {
    deleteArchitectWorkspaceMockRows(selectedIds);
    setSelectedIds(new Set());
    bumpDataVersion();
  }, [bumpDataVersion, selectedIds]);

  const insertRow = useCallback(() => {
    const id = `new-${crypto.randomUUID()}`;
    const program = programFilter.trim().length > 0 ? programFilter : "Care Management";
    const nextRow: ArchitectRosterRow = {
      id,
      caseId: "CR-NEW",
      memberName: "New member (mock)",
      program,
      status: "Pending",
      nextReview: "2026-05-30",
      detailNote: "Inserted row — replace with real workflow later.",
    };
    insertArchitectWorkspaceMockRow(nextRow);
    setSelectedIds(new Set([id]));
    bumpDataVersion();
  }, [bumpDataVersion, programFilter]);

  const refreshMockData = useCallback(() => {
    resetArchitectWorkspaceMockStore();
    setSelectedIds(new Set());
    bumpDataVersion();
    setIamStatsVersion((v) => v + 1);
  }, [bumpDataVersion]);

  const handleSelectProgramFromTypeahead = useCallback((program: string) => {
    setProgramFilter(program);
    setTypeaheadQuery("");
  }, []);

  useLayoutEffect(() => {
    const el = selectAllRef.current;
    if (el) {
      el.indeterminate = someVisibleSelected && !allVisibleSelected;
    }
  }, [allVisibleSelected, someVisibleSelected]);

  return (
    <div className="flex w-full flex-col gap-4">
      <ArchitectWorkspaceChrome
        activeTab={activeTab}
        tabLabels={ARCHITECT_WORKSPACE_TABS}
        advancedFiltersOpen={advancedOpen}
        onTabChange={setActiveTab}
        onAdvancedFiltersOpenChange={setAdvancedOpen}
        onRefreshMockData={refreshMockData}
        onAddTabRequest={() => setAddTabOpen(true)}
      />

      <div className="flex flex-col gap-4 pb-8">
        <SolutionSummaryPanels counts={summary} />

        <IamRoleSummaryPanels counts={roleCounts} />

        {iamStatsError !== null ? (
          <div
            className="rounded-[10px] border border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive"
            role="status"
          >
            People counts unavailable: {iamStatsError}
          </div>
        ) : null}

        <RegisteredServicesPanel initialResult={registeredServicesBootstrap} />

        <ArchitectRosterFiltersPanel
          open={advancedOpen}
          onOpenChange={setAdvancedOpen}
          keyword={{ value: keyword, onChange: setKeyword }}
          programTypeahead={{
            query: typeaheadQuery,
            onQueryChange: setTypeaheadQuery,
            matches: typeaheadMatches,
            onSelectProgram: handleSelectProgramFromTypeahead,
            onOpenLookup: () => setLookupOpen(true),
            activeProgramExact: programFilter,
            onClearProgramFilter: () => setProgramFilter(""),
          }}
          statusMultiSelect={{
            selected: multiSelected,
            query: multiQuery,
            onQueryChange: setMultiQuery,
            pool: multiPool,
            onAdd: (status) => {
              setMultiSelected((prev) => [...prev, status]);
              setMultiQuery("");
            },
            onRemove: (status) => {
              setMultiSelected((prev) => prev.filter((t) => t !== status));
            },
          }}
        />

        {workspaceError !== null ? (
          <div
            className="rounded-[10px] border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            role="alert"
          >
            <p className="font-medium">Workspace data could not be loaded.</p>
            <p className="mt-1 text-xs opacity-90">{workspaceError}</p>
          </div>
        ) : null}

        {workspacePending && rosterRows.length === 0 && workspaceError === null ? (
          <p className="text-sm text-muted-foreground">Loading workspace…</p>
        ) : null}

        <ArchitectRosterTablePanel
          title={activeTab}
          description="Roster and summary are loaded via fetchArchitectWorkspaceData (mock). Sorting and filters are sent on each request."
          isLoading={workspacePending}
          rows={rosterRows}
          sorts={sorts}
          onSort={handleSort}
          selectedIds={selectedIds}
          onToggleRow={toggleRow}
          allVisibleSelected={allVisibleSelected}
          selectAllCheckboxRef={selectAllRef}
          onToggleSelectAllVisible={toggleSelectAllVisible}
          expandedRowId={expandedId}
          onExpandedRowChange={setExpandedId}
          onOpenFilterDialog={() => setFiltersOpen(true)}
          onInsertRow={insertRow}
          onDeleteSelected={deleteSelected}
          deleteSelectedDisabled={selectedIds.size === 0 || workspacePending}
        />
      </div>

      <ArchitectWorkspaceDialogs
        filterDialog={{
          open: filtersOpen,
          onOpenChange: setFiltersOpen,
          programValue: filterDraft.program,
          statusValue: filterDraft.status,
          onProgramChange: (program) =>
            setFilterDraft((d) => ({ ...d, program })),
          onStatusChange: (status) => setFilterDraft((d) => ({ ...d, status })),
          onClear: () => {
            setFilterDraft({ program: "", status: "" });
            setAppliedFilter({ program: "", status: "" });
          },
          onApply: () => {
            setAppliedFilter({ ...filterDraft });
            setFiltersOpen(false);
          },
        }}
        lookupDialog={{
          open: lookupOpen,
          onOpenChange: setLookupOpen,
          programOptions: PROGRAM_TYPEAHEAD_OPTIONS,
          onSelectProgram: (program) => {
            setProgramFilter(program);
            setLookupOpen(false);
          },
        }}
        addTabDialog={{
          open: addTabOpen,
          onOpenChange: setAddTabOpen,
        }}
      />
    </div>
  );
}
