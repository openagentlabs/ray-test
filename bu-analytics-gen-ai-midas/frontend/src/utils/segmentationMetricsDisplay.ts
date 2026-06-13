/**
 * Display helpers for segmentation validation metrics.
 * Avoids misleading "0.000" when values are small but non-zero (IV, χ² p).
 * Very small χ² p-values are shown as less than 0.0001 (no long decimals or scientific notation).
 */

const WOE_EPS = 0.5;

/**
 * Pool-based total IV from segment counts (matches backend WoEIVCalculator + segment-pool TE/TN).
 * Used only as a display fallback when validation.total_iv is still 0 (stale API / rounding).
 */
export type SegmentCountRow = {
  n: number;
  e: number;
};

/** Pool event / non-event counts from segment rows (same basis as backend WoEIVCalculator). */
export function segmentCountRowsFromSegments(
  segments: Array<{ record_count?: number; size?: number; event_count?: number }> | null | undefined
): SegmentCountRow[] {
  if (!Array.isArray(segments)) return [];
  return segments
    .map((s) => ({
      n: Number(s.record_count ?? s.size ?? 0),
      e: Number(s.event_count ?? 0),
    }))
    .filter((r) => r.n > 0);
}

/**
 * Per-segment WoE and IV contribution from pooled counts (matches backend epsilon-smoothed IV).
 * Used when API leaves iv_contribution/woe at 0 (e.g. stale session) but event counts are valid.
 */
export function perSegmentWoeIvContributions(
  segments: Array<{ record_count?: number; size?: number; event_count?: number }> | null | undefined
): { woe: number; iv_contribution: number }[] {
  const rows = segmentCountRowsFromSegments(segments);
  if (rows.length < 2) return rows.map(() => ({ woe: 0, iv_contribution: 0 }));
  let te = 0;
  for (const r of rows) te += r.e;
  const pool = rows.reduce((a, r) => a + r.n, 0);
  const tn = pool - te;
  if (te <= 0 || tn <= 0) return rows.map(() => ({ woe: 0, iv_contribution: 0 }));
  return rows.map((r) => {
    const ne = r.n - r.e;
    const distE = (r.e + WOE_EPS) / (te + WOE_EPS);
    const distN = (ne + WOE_EPS) / (tn + WOE_EPS);
    if (distE <= 0 || distN <= 0) return { woe: 0, iv_contribution: 0 };
    const woe = Math.log(distN / distE);
    const iv_contribution = (distN - distE) * woe;
    return { woe, iv_contribution };
  });
}

export function fallbackTotalIvFromSegments(
  segments: Array<{ record_count?: number; size?: number; event_count?: number }> | null | undefined
): number {
  const parts = perSegmentWoeIvContributions(segments);
  if (parts.length < 2) return 0;
  return parts.reduce((a, p) => a + p.iv_contribution, 0);
}

export function displayTotalIv(
  validationTotalIv: unknown,
  segments: Array<{ record_count?: number; size?: number; event_count?: number }> | null | undefined
): string {
  const api = validationTotalIv == null || validationTotalIv === '' ? NaN : Number(validationTotalIv);
  if (Number.isFinite(api) && Math.abs(api) > 1e-12) {
    return formatSegmentationTotalIv(api);
  }
  return formatSegmentationTotalIv(fallbackTotalIvFromSegments(segments));
}

export function formatSegmentationTotalIv(iv: unknown): string {
  if (iv == null || iv === '') return 'N/A';
  const x = Number(iv);
  if (!Number.isFinite(x)) return 'N/A';
  if (x === 0) return '0.000';
  const ax = Math.abs(x);
  if (ax < 0.0005) return x.toExponential(2);
  if (ax < 0.01) return x.toFixed(4);
  return x.toFixed(3);
}

const CHI_SQ_P_CUTOFF = 0.0001;

/**
 * Numeric / symbolic string for χ² p (no leading "p = "). Values below 1e-4 render as '< 0.0001'.
 */
export function formatSegmentationChiSquaredP(p: unknown, significant?: boolean): string {
  if (p == null || p === '') return 'N/A';
  const x = Number(p);
  if (!Number.isFinite(x)) return 'N/A';
  if (x < 0) return 'N/A';
  if (x === 0) {
    return significant ? '< 0.0001' : '0';
  }
  if (x < CHI_SQ_P_CUTOFF) {
    return '< 0.0001';
  }
  if (x < 0.01) return x.toFixed(6);
  return x.toFixed(4);
}

/**
 * Full phrase for UI lines: "p = 0.034" or "p < 0.0001" (avoids "p = < 0.0001").
 */
export function formatSegmentationChiSquaredPLabel(p: unknown, significant?: boolean): string {
  const inner = formatSegmentationChiSquaredP(p, significant);
  if (inner === 'N/A') return 'p = N/A';
  if (inner.startsWith('<')) return `p ${inner}`;
  return `p = ${inner}`;
}

/**
 * OOS validation (`segmentation_validation._validate_out_of_sample`) sends
 * `train_event_rate` / `oos_event_rate` as percent on 0–100 scale (same as `SegmentDetail.event_rate`),
 * not as a 0–1 proportion. Do not multiply by 100 again for display.
 */
export function formatOosEventRatePercent(rate: unknown): string {
  const x = Number(rate);
  if (!Number.isFinite(x)) return '0.00%';
  return `${x.toFixed(2)}%`;
}

/** `event_rate_drift` is |oos − train| in percentage points (already pp, not proportion). */
export function formatOosEventRateDriftPp(drift: unknown): string {
  const x = Number(drift);
  if (!Number.isFinite(x)) return '0.00pp';
  return `${Math.abs(x).toFixed(2)}pp`;
}

/**
 * Short text for merge recommendation cards (sidebar). Backend now sends concise strings;
 * this still collapses legacy verbose "Reliability check failed: …" payloads from older sessions.
 */
export function formatMergeRecommendationExplanationForDisplay(
  raw: string | null | undefined,
  failedCondition?: string
): string {
  let s = String(raw ?? '').trim();
  if (!s) return '';

  const legacyReliability = 'Reliability check failed:';
  if (s.startsWith(legacyReliability)) {
    const inner = s.slice(legacyReliability.length).trim();
    const chunks = inner
      .split(';')
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 6);
    const collapsed = chunks
      .map((c) => {
        const m = c.match(/^'([^']+)'\s+has\s+(\d+)\s+records.*?has\s+(\d+)\s+events/i);
        if (m) return `${m[1]} ${m[2]}r/${m[3]}e`;
        return c.length > 52 ? `${c.slice(0, 49)}…` : c;
      })
      .join(' · ');
    return collapsed ? `Below mins: ${collapsed}` : s;
  }

  if (failedCondition === 'practical_separation') {
    const m = s.match(/Event rate difference\s*\(([\d.]+)pp\)\s*is below\s*practical threshold\s*\(([\d.]+)pp\)/i);
    if (m) return `${m[1]}pp < ${m[2]}pp — rates too close.`;
  }

  if (s.length > 220) return `${s.slice(0, 217)}…`;
  return s;
}
