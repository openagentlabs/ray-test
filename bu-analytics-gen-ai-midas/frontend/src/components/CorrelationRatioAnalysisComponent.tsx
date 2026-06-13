import React, { useCallback, useEffect, useState, useMemo, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { Loader, AlertTriangle, BarChart3, FileDown, Activity } from 'lucide-react';
import {
  correlationRatioService,
  CorrelationRatioSection,
  CorrelationRatioAnalysisResponse,
} from '../services/correlationRatioService';
import { downloadExcelWorkbookWithCharts, flushChartDraw, type ReportCell } from '../utils/excelReportWithCharts';

interface Props {
  datasetId: string | null;
  targetVariable: string;
  currentStep: number;
}

interface CachedCorrelationRatio {
  sections: CorrelationRatioSection[];
  analysisTimestamp?: string;
  key: string;
  ts: number;
}

const ratioCache = new Map<string, CachedCorrelationRatio>();
const CACHE_MS = 10 * 60 * 1000;

function getDataScope(): string {
  try {
    const raw = sessionStorage.getItem('dataset_config');
    if (raw) {
      const p = JSON.parse(raw) as { data_scope?: string };
      if (p?.data_scope) return String(p.data_scope);
    }
  } catch {
    /* ignore */
  }
  return 'entire';
}

/** Map η ∈ [0,1] onto matplotlib coolwarm with center at η=0.5 (same diverging use as centered correlation). */
function etaToCoolwarmColor(eta: number | null | undefined, isDark: boolean): string {
  if (eta == null || Number.isNaN(eta)) {
    return isDark ? '#4b5563' : '#d1d5db';
  }
  const x = Math.max(-1, Math.min(1, 2 * Number(eta) - 1));
  const stops = [
    { t: -1, r: 59, g: 76, b: 192 },
    { t: 0, r: 221, g: 221, b: 221 },
    { t: 1, r: 180, g: 4, b: 38 },
  ];
  let a = stops[0];
  let b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (x <= stops[i + 1].t) {
      a = stops[i];
      b = stops[i + 1];
      break;
    }
  }
  const span = b.t - a.t || 1;
  const u = (x - a.t) / span;
  const r = Math.round(a.r + (b.r - a.r) * u);
  const g = Math.round(a.g + (b.g - a.g) * u);
  const bl = Math.round(a.b + (b.b - a.b) * u);
  return `rgb(${r},${g},${bl})`;
}

function methodologyAoA(): (string | number)[][] {
  return [
    ['Section', 'Detail'],
    [
      'Correlation ratio (η)',
      'Measures how much of the variance in a numeric variable is explained by group means of a categorical variable (0–1).',
    ],
    [
      'Heatmap',
      'Categorical / low-cardinality variables on the vertical axis, numeric variables on the horizontal axis; coolwarm-style colors aligned with the correlation matrix heatmap.',
    ],
    ['Workbook', 'Methodology, Report info, η matrix table, and a PNG of the heatmap when shown.'],
  ];
}

/** Coerce API matrix cells to number | null for display (JSON may carry strings). */
function normalizeEtaMatrix(
  matrix: unknown[][] | undefined,
  nRows: number,
  nCols: number
): (number | null)[][] | null {
  if (!matrix || !Array.isArray(matrix) || matrix.length !== nRows) return null;
  const out: (number | null)[][] = [];
  for (let ri = 0; ri < nRows; ri++) {
    const row = matrix[ri];
    if (!Array.isArray(row)) return null;
    const pad = [...row];
    while (pad.length < nCols) pad.push(null);
    if (pad.length > nCols) pad.length = nCols;
    const cells: (number | null)[] = [];
    for (let ci = 0; ci < nCols; ci++) {
      const v = pad[ci];
      if (v == null || v === '') {
        cells.push(null);
        continue;
      }
      const n = typeof v === 'number' ? v : Number(v);
      cells.push(Number.isFinite(n) ? n : null);
    }
    out.push(cells);
  }
  return out;
}

function pickHeatmapSection(sections: CorrelationRatioSection[]): CorrelationRatioSection | null {
  const hm = sections.find((s) => s.analysis_kind === 'correlation_ratio_categorical_numeric_heatmap');
  if (!hm?.matrix?.length || !hm.row_labels?.length || !hm.column_labels?.length) return null;
  const rowLabels = hm.row_labels.map((x) => String(x));
  const colLabels = hm.column_labels.map((x) => String(x));
  const rows = rowLabels.length;
  const cols = colLabels.length;
  const normalized = normalizeEtaMatrix(hm.matrix as unknown[][], rows, cols);
  if (!normalized) return null;
  return {
    ...hm,
    row_labels: rowLabels,
    column_labels: colLabels,
    matrix: normalized,
  };
}

const CorrelationRatioAnalysisComponent: React.FC<Props> = ({ datasetId, targetVariable, currentStep }) => {
  const { isDark } = useTheme();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sections, setSections] = useState<CorrelationRatioSection[]>([]);
  const [analysisTimestamp, setAnalysisTimestamp] = useState<string | undefined>();
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);

  const mountedRef = useRef(true);
  const isRunningRef = useRef(false);
  const heatmapRootRef = useRef<HTMLDivElement | null>(null);

  const cacheKey = useMemo(() => {
    if (!datasetId || !targetVariable?.trim()) return '';
    return `${datasetId}-${targetVariable.trim()}-correlation-ratio-${getDataScope()}`;
  }, [datasetId, targetVariable]);

  const heatmapSection = useMemo(() => pickHeatmapSection(sections), [sections]);

  const runAnalysis = useCallback(async () => {
    if (!datasetId || !targetVariable?.trim()) return;
    if (isRunningRef.current) return;
    isRunningRef.current = true;
    setIsAnalyzing(true);
    setError(null);
    try {
      const res: CorrelationRatioAnalysisResponse = await correlationRatioService.analyze({
        dataset_id: datasetId,
        target_variable: targetVariable.trim(),
      });
      if (!mountedRef.current) return;
      if (!res.success) {
        setError(res.message || 'Correlation ratio analysis failed');
        setSections([]);
        setAnalysisTimestamp(undefined);
        return;
      }
      const next = Array.isArray(res.sections) ? res.sections : [];
      setSections(next);
      setAnalysisTimestamp(res.analysis_timestamp);
      const ck = `${datasetId}-${targetVariable.trim()}-correlation-ratio-${getDataScope()}`;
      ratioCache.set(ck, {
        sections: next,
        analysisTimestamp: res.analysis_timestamp,
        key: ck,
        ts: Date.now(),
      });
    } catch (e: unknown) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Request failed');
        setSections([]);
      }
    } finally {
      isRunningRef.current = false;
      if (mountedRef.current) setIsAnalyzing(false);
    }
  }, [datasetId, targetVariable]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (currentStep !== 3 || !datasetId || !targetVariable?.trim()) {
      setSections([]);
      setError(null);
      return;
    }
    const key = `${datasetId}-${targetVariable.trim()}-correlation-ratio-${getDataScope()}`;
    const hit = ratioCache.get(key);
    if (hit && Date.now() - hit.ts < CACHE_MS) {
      setSections(hit.sections);
      setAnalysisTimestamp(hit.analysisTimestamp);
      setError(null);
      return;
    }
    void runAnalysis();
  }, [datasetId, targetVariable, currentStep, cacheKey, runAnalysis]);

  useEffect(() => {
    const onScope = (ev: Event) => {
      const d = (ev as CustomEvent<{ dataset_id?: string }>).detail;
      if (d?.dataset_id === datasetId) {
        for (const k of ratioCache.keys()) {
          if (k.startsWith(`${datasetId}-`) && k.includes('-correlation-ratio-')) {
            ratioCache.delete(k);
          }
        }
        void runAnalysis();
      }
    };
    window.addEventListener('datasetScopeChanged', onScope as EventListener);
    return () => window.removeEventListener('datasetScopeChanged', onScope as EventListener);
  }, [datasetId, targetVariable, runAnalysis]);

  const downloadReportExcel = async () => {
    if (!sections.length || !datasetId) {
      alert('Run analysis first, then download the report.');
      return;
    }
    setIsExcelDownloading(true);
    try {
      await flushChartDraw();

      const infoRows: ReportCell[][] = [
        ['Field', 'Value'],
        ['Dataset ID', datasetId],
        ['Target variable', targetVariable],
        ['Exported (UTC)', new Date().toISOString()],
        ['Analysis timestamp (API)', analysisTimestamp || '—'],
      ];

      const sheets: { name: string; rows: ReportCell[][] }[] = [
        { name: 'Methodology', rows: methodologyAoA() },
        { name: 'Report info', rows: infoRows },
      ];

      const hm = pickHeatmapSection(sections);
      if (hm?.matrix?.length && hm.row_labels?.length && hm.column_labels?.length) {
        const header: ReportCell[] = ['(categorical)', ...hm.column_labels];
        const matrixRows: ReportCell[][] = [header];
        for (let ri = 0; ri < hm.row_labels.length; ri++) {
          const row = hm.matrix[ri] || [];
          matrixRows.push([hm.row_labels[ri], ...row.map((v) => (v == null ? '' : v))]);
        }
        sheets.push({ name: 'Eta matrix', rows: matrixRows });
      }

      const chartPngs: { sheetName: string; base64Png: string; width?: number; height?: number }[] = [];

      if (heatmapRootRef.current) {
        const html2canvas = (await import('html2canvas')).default;
        const el = heatmapRootRef.current;
        const win = el.ownerDocument.defaultView;
        const vw = win?.innerWidth ?? 1280;
        const vh = win?.innerHeight ?? 800;
        // html2canvas defaults windowWidth to the viewport, which clips wide scrollable heatmaps.
        const captureW = Math.ceil(Math.max(vw, el.scrollWidth, el.getBoundingClientRect().width) + 32);
        const captureH = Math.ceil(Math.max(vh, el.scrollHeight, el.getBoundingClientRect().height) + 32);
        const canvas = await html2canvas(el, {
          backgroundColor: isDark ? '#1f2937' : '#ffffff',
          scale: 2,
          useCORS: true,
          scrollX: 0,
          scrollY: 0,
          windowWidth: captureW,
          windowHeight: captureH,
          onclone(_clonedDoc, clonedRoot) {
            clonedRoot.style.overflow = 'visible';
            clonedRoot.style.maxHeight = 'none';
            clonedRoot.style.height = 'auto';
            clonedRoot.style.width = 'max-content';
            const tbl = clonedRoot.querySelector('table');
            if (tbl instanceof HTMLElement) {
              tbl.style.width = 'max-content';
              tbl.style.maxWidth = 'none';
            }
            clonedRoot.querySelectorAll('.sticky').forEach((node) => {
              if (!(node instanceof HTMLElement)) return;
              node.style.position = 'relative';
              node.style.left = 'auto';
              node.style.top = 'auto';
              node.style.zIndex = 'auto';
            });
          },
        });
        const dataUrl = canvas.toDataURL('image/png');
        const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
        if (base64) {
          // Preserve aspect ratio in Excel; cap longest edge only for display size (PNG stays full res).
          const maxEdge = 2400;
          let dispW = canvas.width;
          let dispH = canvas.height;
          const longest = Math.max(dispW, dispH);
          if (longest > maxEdge) {
            const s = maxEdge / longest;
            dispW = Math.round(dispW * s);
            dispH = Math.round(dispH * s);
          }
          chartPngs.push({
            sheetName: 'Eta heatmap',
            base64Png: base64,
            width: dispW,
            height: dispH,
          });
        }
      }

      const safe = datasetId.replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `Correlation_Ratio_${safe}_${new Date().toISOString().split('T')[0]}.xlsx`;

      await downloadExcelWorkbookWithCharts({
        filename: fname,
        sheets,
        charts: chartPngs.length ? chartPngs : undefined,
      });
    } catch (e) {
      console.error('Correlation ratio Excel export failed:', e);
      alert('Could not build the Excel file. Try again after analysis finishes loading.');
    } finally {
      setIsExcelDownloading(false);
    }
  };

  const hasData = useMemo(() => Boolean(heatmapSection), [heatmapSection]);

  if (!datasetId || !targetVariable?.trim()) {
    return (
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <span className="text-yellow-800 dark:text-yellow-300 font-medium">Dataset Required</span>
        </div>
        <p className="text-yellow-700 dark:text-yellow-400 text-sm mt-1">
          Ensure a dataset is loaded and a target variable is configured.
        </p>
      </div>
    );
  }

  if (isAnalyzing) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-6 text-center">
        <Loader className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Running Correlation Ratio (η) Analysis</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Computing η for categorical / low-cardinality predictors vs numeric columns…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-red-600" />
          <span className="text-red-800 dark:text-red-300 font-medium">Analysis Failed</span>
        </div>
        <p className="text-red-700 dark:text-red-400 text-sm mt-1">{error}</p>
        <button
          type="button"
          onClick={() => void runAnalysis()}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
        >
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
        <BarChart3 className="h-8 w-8 text-gray-400 mx-auto mb-3" />
        <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Correlation ratio (η)</h3>
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          No η results for this target and scope (cardinality limits may exclude some columns).
        </p>
        <button
          type="button"
          onClick={() => void runAnalysis()}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors text-sm"
        >
          Run Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {heatmapSection && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-5 w-5 shrink-0 text-teal-600" />
            <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm sm:text-base">
              {heatmapSection.title || 'Correlation ratio η (heatmap)'}
            </h4>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            Categorical / low-cardinality variables on the vertical axis, numeric variables on the horizontal axis.
            Colors use the same coolwarm-style scale as the correlation matrix (centered at η = 0.5).
          </p>
          <div ref={heatmapRootRef} className="overflow-auto max-h-[70vh] rounded-md border border-gray-200 dark:border-gray-600">
            <table className="border-collapse text-xs min-w-max">
              <thead>
                <tr>
                  <th className="sticky left-0 z-20 bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-600 px-2 py-1.5 text-left font-medium text-gray-700 dark:text-gray-200">
                    {/* corner */}
                  </th>
                  {(heatmapSection.column_labels || []).map((c) => (
                    <th
                      key={c}
                      className="border border-gray-200 dark:border-gray-600 bg-gray-100 dark:bg-gray-900 px-2 py-1.5 font-medium text-gray-800 dark:text-gray-100 whitespace-nowrap max-w-[10rem] truncate"
                      title={c}
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(heatmapSection.row_labels || []).map((rowName, ri) => (
                  <tr key={`${ri}-${rowName}`}>
                    <th
                      className="sticky left-0 z-10 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-600 px-2 py-1 text-left font-medium text-gray-800 dark:text-gray-100 whitespace-nowrap max-w-[12rem] truncate"
                      title={rowName}
                    >
                      {rowName}
                    </th>
                    {(heatmapSection.matrix?.[ri] || []).map((cell, ci) => {
                      const bg = etaToCoolwarmColor(cell ?? null, isDark);
                      const fg =
                        cell != null && Number(cell) > 0.55 ? 'rgb(255,255,255)' : isDark ? '#f9fafb' : '#111827';
                      return (
                        <td
                          key={`${ri}-${ci}`}
                          className="border border-gray-200 dark:border-gray-600 px-1.5 py-1 text-center font-mono tabular-nums min-w-[3.25rem]"
                          style={{ backgroundColor: bg, color: fg }}
                          title={`${rowName} × ${heatmapSection.column_labels?.[ci]} = ${cell ?? '—'}`}
                        >
                          {cell == null ? '—' : Number(cell).toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
            <span className="font-medium">Scale:</span>
            <span className="inline-flex h-3 w-28 rounded overflow-hidden border border-gray-300 dark:border-gray-600">
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <span key={t} className="flex-1" style={{ backgroundColor: etaToCoolwarmColor(t, isDark) }} />
              ))}
            </span>
            <span>η = 0 → blue</span>
            <span>η = 0.5 → neutral</span>
            <span>η = 1 → red</span>
          </div>
        </div>
      )}

      <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            ratioCache.delete(cacheKey);
            void runAnalysis();
          }}
          disabled={isAnalyzing}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 transition-colors text-sm"
          title="Refresh correlation ratio analysis"
        >
          Refresh Analysis
        </button>
        <button
          type="button"
          onClick={() => void downloadReportExcel()}
          disabled={isAnalyzing || isExcelDownloading || !sections.length}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
          title="Download Excel workbook (.xlsx) with full tables"
        >
          {isExcelDownloading ? (
            <Loader className="h-4 w-4 animate-spin shrink-0" />
          ) : (
            <FileDown className="h-4 w-4 shrink-0" />
          )}
          Download Report
        </button>
      </div>
    </div>
  );
};

export default CorrelationRatioAnalysisComponent;
