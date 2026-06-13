/**
 * Shared visual tokens for the Model Training page (Step 6) and related panels
 * (screener, pruning, RFE) so tables and sections stay consistent.
 */

/**
 * Single row that may display as "Best" in iteration history UIs: the **last** row whose
 * backend `status` is Best Score (case-insensitive). All other rows should show as Completed.
 * Used for both auto and manual training tables.
 */
export function getSoleBestIterationIndexForDisplay(iterations: unknown[] | null | undefined): number | null {
  if (!Array.isArray(iterations) || iterations.length === 0) return null;
  let last = -1;
  iterations.forEach((it, idx) => {
    const st = String((it as { status?: unknown })?.status ?? '')
      .trim()
      .toLowerCase();
    if (st === 'best score') last = idx;
  });
  return last >= 0 ? last : null;
}

/** Gradient header row — use on <thead>; child <th> text forced to light via arbitrary variants */
export const MTA_THEAD =
  'bg-gradient-to-r from-blue-600 via-indigo-600 to-indigo-800 text-white shadow-sm [&_th]:!text-white/95 [&_th]:font-semibold [&_th]:text-[11px] [&_th]:uppercase [&_th]:tracking-wide [&_th]:border-b [&_th]:border-white/15 [&_th]:bg-transparent dark:from-blue-900 dark:via-indigo-900 dark:to-slate-900';

/** Section card: interactive lift on hover */
export const MTA_SECTION =
  'rounded-xl border border-gray-200/90 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm hover:shadow-lg hover:border-blue-300/50 dark:hover:border-blue-800/50 transition-all duration-300';

/** Wrapper around scrollable data tables */
export const MTA_TABLE_SHELL =
  'rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden bg-white dark:bg-gray-900 ring-1 ring-black/[0.04] dark:ring-white/[0.06]';

/** Main page / block titles */
export const MTA_TITLE_PAGE = 'text-xl md:text-2xl font-bold tracking-tight text-gray-900 dark:text-white';

export const MTA_TITLE_SECTION = 'text-lg md:text-xl font-bold tracking-tight text-gray-900 dark:text-white';

/** Numeric step badge (1–6) */
export const MTA_STEP_NUM =
  'inline-flex items-center justify-center min-w-[2.25rem] h-9 px-2 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 text-sm font-black text-white shadow-md ring-2 ring-blue-400/30 dark:ring-indigo-400/20';

/** Letter step chip (Step A / Step B) — pale blue pill, bold blue uppercase label */
export const MTA_STEP_LETTER_BADGE =
  'inline-flex items-center justify-center px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 border border-blue-100 dark:text-blue-200 dark:bg-blue-950/45 dark:border-blue-800/70';
