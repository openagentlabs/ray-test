import ExcelJS from 'exceljs';

export type ReportCell = string | number | boolean | null | undefined;

export type ReportSheet = { name: string; rows: ReportCell[][] };

export type ReportChartImage = {
  /** Worksheet name (sanitized to Excel rules, max 31 chars). */
  sheetName: string;
  /** Image payload only (no `data:image/...;base64,` prefix). */
  base64Png: string;
  /** Defaults to png (Chart.js); use jpeg for some heatmap responses. */
  extension?: 'png' | 'jpeg';
  width?: number;
  height?: number;
};

function sanitizeExcelSheetName(name: string): string {
  const invalid = /[:\\/?*[\]]/g;
  let s = name.replace(invalid, ' ').trim();
  if (!s) s = 'Sheet';
  return s.slice(0, 31);
}

/** Strip a data URL to raw base64 for ExcelJS. */
export function stripPngDataUrlToBase64(dataUrl: string): string {
  const m = dataUrl.match(/^data:image\/png;base64,(.+)$/i);
  if (m) return m[1];
  return dataUrl.replace(/^data:image\/\w+;base64,/i, '');
}

/** Capture Chart.js instance as PNG base64 (no data URL prefix). */
export function chartToPngBase64(
  chart: { toBase64Image?: (type?: string, quality?: unknown) => string } | null | undefined
): string | null {
  if (!chart || typeof chart.toBase64Image !== 'function') return null;
  try {
    const dataUrl = chart.toBase64Image('image/png', 1);
    return stripPngDataUrlToBase64(dataUrl);
  } catch {
    return null;
  }
}

/** Let the browser paint the chart canvas before export. */
export function flushChartDraw(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
}

/**
 * Load a displayed heatmap or image URL (blob:, data:, or http) as base64 for ExcelJS.addImage.
 */
export async function imageUrlToExcelImage(
  url: string
): Promise<{ base64: string; extension: 'png' | 'jpeg' } | null> {
  if (!url?.trim()) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    const dataUrl: string = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('read failed'));
      reader.readAsDataURL(blob);
    });
    const m = dataUrl.match(/^data:image\/(png|jpeg|jpg);base64,(.+)$/i);
    if (!m) return null;
    const kind = m[1].toLowerCase();
    const ext: 'png' | 'jpeg' = kind === 'png' ? 'png' : 'jpeg';
    return { base64: m[2], extension: ext };
  } catch {
    return null;
  }
}

/**
 * Build an .xlsx workbook with data sheets plus optional PNG chart sheets (one image per sheet).
 */
export async function downloadExcelWorkbookWithCharts(opts: {
  filename: string;
  sheets: ReportSheet[];
  charts?: ReportChartImage[];
}): Promise<void> {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'MIDAS';
  wb.created = new Date();

  for (const s of opts.sheets) {
    const ws = wb.addWorksheet(sanitizeExcelSheetName(s.name));
    for (const row of s.rows) {
      ws.addRow(row.map((c) => (c === undefined ? '' : c)));
    }
  }

  if (opts.charts?.length) {
    for (const ch of opts.charts) {
      if (!ch.base64Png?.length) continue;
      const ws = wb.addWorksheet(sanitizeExcelSheetName(ch.sheetName));
      const imageId = wb.addImage({
        base64: ch.base64Png,
        extension: ch.extension ?? 'png',
      });
      ws.addImage(imageId, {
        tl: { col: 0, row: 0 },
        ext: { width: ch.width ?? 720, height: ch.height ?? 420 },
      });
    }
  }

  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = opts.filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
