import type { ArchitectRosterRow } from "@/lib/types/architect-workspace";

/** Canonical roster seed — replace with microservice-backed source of truth when live. */
export const ARCHITECT_ROSTER_SEED_ROWS: readonly ArchitectRosterRow[] = Object.freeze([
  {
    id: "r1",
    caseId: "CR-10482",
    memberName: "Jordan Ellis",
    program: "Care Management",
    status: "Active",
    nextReview: "2026-05-22",
    detailNote:
      "High utilizer — weekly outreach scheduled. PCP aligned on med reconciliation.",
  },
  {
    id: "r2",
    caseId: "CR-10421",
    memberName: "Sam Rivera",
    program: "Transitional Care",
    status: "Pending",
    nextReview: "2026-05-18",
    detailNote:
      "Post-discharge follow-up; transportation barrier noted for first visit.",
  },
  {
    id: "r3",
    caseId: "CR-10307",
    memberName: "Avery Chen",
    program: "Behavioral Health",
    status: "On hold",
    nextReview: "2026-06-01",
    detailNote:
      "Member requested pause until new insurance card arrives (mock).",
  },
  {
    id: "r4",
    caseId: "CR-10244",
    memberName: "Morgan Blake",
    program: "Care Management",
    status: "Closed",
    nextReview: "2026-04-30",
    detailNote: "Goals met; warm handoff to community program (mock).",
  },
]);
