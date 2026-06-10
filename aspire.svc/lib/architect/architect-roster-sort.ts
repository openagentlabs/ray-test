import type {
  ArchitectRosterRow,
  ArchitectRosterSortEntry,
  ArchitectRosterSortKey,
} from "@/lib/types/architect-workspace";

function compareSortKey(
  a: ArchitectRosterRow,
  b: ArchitectRosterRow,
  key: ArchitectRosterSortKey,
): number {
  const va = a[key];
  const vb = b[key];
  return va.localeCompare(vb, undefined, { numeric: true, sensitivity: "base" });
}

export function sortArchitectRosterRows(
  rows: readonly ArchitectRosterRow[],
  sorts: readonly ArchitectRosterSortEntry[],
): ArchitectRosterRow[] {
  if (sorts.length === 0) {
    return [...rows];
  }
  return [...rows].sort((a, b) => {
    for (const { column, direction } of sorts) {
      const c = compareSortKey(a, b, column);
      if (c !== 0) {
        return direction === "asc" ? c : -c;
      }
    }
    return 0;
  });
}
