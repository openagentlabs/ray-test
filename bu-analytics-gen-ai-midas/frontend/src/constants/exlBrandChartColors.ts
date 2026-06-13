/** EXL brand palette — use only these hex values for chart canvas, datasets, axes, grids, and tooltips. */
export const EXL_ORANGE = '#FB4E0B';
export const EXL_SLATE = '#2e3643';
export const EXL_MIDNIGHT = '#005071';
export const EXL_LIGHT_BLUE = '#dcf3fa';

export function exlRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
