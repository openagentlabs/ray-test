/**
 * Shared tokens + types used by RFEStep and FeatureReviewStep.
 *
 * Design intent:
 * - Use the wireframe's primary orange (#FB4E0B) as the accent, consistent with
 *   the rest of ModelBuilder.tsx.
 * - Expose dark-mode-aware color tokens as a single function to avoid sprinkling
 *   hex codes across components.
 */

export const RFE_PRIMARY = '#FB4E0B';
export const RFE_GREEN = '#16A34A';
export const RFE_RED = '#DC2626';
export const RFE_AMBER = '#D97706';
export const RFE_BLUE = '#2563EB';

export interface RfeStepTheme {
  isDarkMode: boolean;
  panelBg: string;
  panelBorder: string;
  textMuted: string;
  textStrong: string;
  gridLine: string;
  tableZebra: string;
  tableRow: string;
  accent: string;
  accentSoft: string;
  positive: string;
  negative: string;
  warning: string;
}

export function getRfeTheme(isDarkMode: boolean): RfeStepTheme {
  return isDarkMode
    ? {
        isDarkMode: true,
        panelBg: 'bg-slate-900/60',
        panelBorder: 'border-slate-700',
        textMuted: 'text-gray-300',
        textStrong: 'text-white',
        gridLine: '#1f2937',
        tableZebra: 'bg-slate-900/50',
        tableRow: 'bg-slate-950',
        accent: RFE_PRIMARY,
        accentSoft: 'rgba(251, 78, 11, 0.18)',
        positive: '#22c55e',
        negative: '#f87171',
        warning: '#f59e0b',
      }
    : {
        isDarkMode: false,
        panelBg: 'bg-white',
        panelBorder: 'border-gray-200',
        textMuted: 'text-gray-500',
        textStrong: 'text-gray-900',
        gridLine: '#e5e7eb',
        tableZebra: 'bg-slate-50',
        tableRow: 'bg-white',
        accent: RFE_PRIMARY,
        accentSoft: 'rgba(251, 78, 11, 0.1)',
        positive: RFE_GREEN,
        negative: RFE_RED,
        warning: RFE_AMBER,
      };
}

export function fmt(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return `${(value * 100).toFixed(digits)}%`;
}

export type MtaSubStep = 'lock' | 'screener' | 'rfe' | 'review' | 'completed' | 'train';
