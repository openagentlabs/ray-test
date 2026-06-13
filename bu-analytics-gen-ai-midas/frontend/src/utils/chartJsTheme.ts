/**
 * Chart.js v4 theming for light / dark UI. Canvas text does not inherit CSS; set `color` and scale colors explicitly.
 */

export function chartJsDefaultFontColor(isDark: boolean): string {
  return isDark ? '#e5e7eb' : '#374151';
}

export function chartJsScaleBorder(isDark: boolean) {
  return {
    display: true,
    color: isDark ? 'rgba(148, 163, 184, 0.4)' : 'rgba(15, 23, 42, 0.12)',
  };
}

export function chartJsTooltipColors(isDark: boolean) {
  if (isDark) {
    return {
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      titleColor: '#f8fafc',
      bodyColor: '#e2e8f0',
      borderColor: 'rgba(148, 163, 184, 0.45)',
      borderWidth: 1,
    };
  }
  return {
    backgroundColor: 'rgba(15, 23, 42, 0.88)',
    titleColor: '#ffffff',
    bodyColor: '#ffffff',
    borderColor: 'rgba(255, 255, 255, 0.15)',
    borderWidth: 1,
  };
}
