import type { ArchitectIamRoleSummaryCounts } from "@/lib/types/architect-workspace";

/**
 * Maps IAM `GetUserTypeStats` buckets (display name or code) onto the five architect workspace panels.
 * Each stat row is assigned to at most one panel (first matching rule wins).
 */
export function mapUserTypeStatsToRolePanels(
  entries: readonly { readonly typeName: string; readonly count: number }[],
): ArchitectIamRoleSummaryCounts {
  let admins = 0;
  let solutionOwners = 0;
  let architects = 0;
  let softwareDevs = 0;
  let devops = 0;

  for (const e of entries) {
    const n = Number.isFinite(e.count) ? e.count : 0;
    if (n <= 0) {
      continue;
    }
    const norm = e.typeName.trim().toLowerCase().replace(/\s+/g, " ");

    if (/(^|\s)devops(\s|$)|dev ops/.test(norm)) {
      devops += n;
      continue;
    }
    if (/^admin$|^administrator$/.test(norm) || norm === "admin") {
      admins += n;
      continue;
    }
    if (/solution owner/.test(norm)) {
      solutionOwners += n;
      continue;
    }
    if (/^architect$|^arch$/.test(norm)) {
      architects += n;
      continue;
    }
    if (
      /\bsoftware\b/.test(norm) ||
      /\bdeveloper\b/.test(norm) ||
      /^dev$/.test(norm) ||
      /software dev/.test(norm)
    ) {
      softwareDevs += n;
      continue;
    }
  }

  return { admins, solutionOwners, architects, softwareDevs, devops };
}
