import React from 'react';
import { X, LineChart, BarChart3, Info } from 'lucide-react';
import { MonotonicityResults, CSIRow } from '../types/modelEvaluation';

interface PSICSIModalProps {
  isOpen: boolean;
  onClose: () => void;
  monotonicity: MonotonicityResults | undefined;
}

const formatPct = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(2)}%`;
};

const formatNum = (value?: number | null, digits = 3) => {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return value.toFixed(digits);
};

const PSICSIModal: React.FC<PSICSIModalProps> = ({ isOpen, onClose, monotonicity }) => {
  if (!isOpen || !monotonicity) return null;

  const csiData: CSIRow[] = monotonicity.csi || [];
  const sortedCSI = [...csiData].sort((a, b) => b.CSI - a.CSI);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Stable':
        return 'text-emerald-600 bg-emerald-50 dark:text-emerald-200 dark:bg-emerald-900/30';
      case 'Moderate':
        return 'text-amber-600 bg-amber-50 dark:text-amber-200 dark:bg-amber-900/30';
      case 'Significant':
        return 'text-red-600 bg-red-50 dark:text-red-200 dark:bg-red-900/30';
      default:
        return 'text-gray-600 bg-gray-50 dark:text-gray-300 dark:bg-slate-800';
    }
  };

  const getPSIStatusColor = (psi: number) => {
    if (psi < 0.1) return 'text-emerald-600 bg-emerald-50 dark:text-emerald-200 dark:bg-emerald-900/30';
    if (psi < 0.25) return 'text-amber-600 bg-amber-50 dark:text-amber-200 dark:bg-amber-900/30';
    return 'text-red-600 bg-red-50 dark:text-red-200 dark:bg-red-900/30';
  };

  const getPSIStatus = (psi: number) => {
    if (psi < 0.1) return 'Stable';
    if (psi < 0.25) return 'Moderate';
    return 'Significant';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50" onClick={onClose}>
      <div
        className="bg-white dark:bg-slate-900 rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-slate-700 bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-slate-800 rounded-lg">
              <BarChart3 className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">PSI & CSI Analysis</h2>
              <p className="text-sm text-gray-600 dark:text-gray-300">Population Stability Index & Characteristic Stability Index</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5 text-gray-500 dark:text-gray-300" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* PSI Section */}
          {monotonicity.psi !== undefined && monotonicity.psi !== null && (
            <div className="border border-purple-200 dark:border-slate-700 rounded-lg p-5 bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
              <div className="flex items-center gap-2 mb-4">
                <LineChart className="h-5 w-5 text-purple-600" />
                <h3 className="text-lg font-semibold text-purple-900 dark:text-purple-200">Population Stability Index (PSI)</h3>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-white dark:bg-slate-900/60 rounded-lg p-4 border border-purple-200 dark:border-slate-700">
                  <div className="text-sm text-gray-600 dark:text-gray-300 mb-1">PSI Value</div>
                  <div className="text-3xl font-bold text-purple-900 dark:text-purple-200">{formatNum(monotonicity.psi, 4)}</div>
                </div>
                <div className="bg-white dark:bg-slate-900/60 rounded-lg p-4 border border-purple-200 dark:border-slate-700">
                  <div className="text-sm text-gray-600 dark:text-gray-300 mb-1">Status</div>
                  <div className={`text-lg font-semibold px-3 py-1 rounded inline-block ${getPSIStatusColor(monotonicity.psi)}`}>
                    {getPSIStatus(monotonicity.psi)}
                  </div>
                </div>
                <div className="bg-white dark:bg-slate-900/60 rounded-lg p-4 border border-purple-200 dark:border-slate-700">
                  <div className="text-sm text-gray-600 dark:text-gray-300 mb-1">Interpretation</div>
                  <div className="text-sm text-gray-800 dark:text-gray-200">
                    {monotonicity.psi < 0.1 ? (
                      <span>No significant population shift - Model is stable</span>
                    ) : monotonicity.psi < 0.25 ? (
                      <span>Moderate population shift - Monitor closely</span>
                    ) : (
                      <span>Significant population shift - Investigate changes</span>
                    )}
                  </div>
                </div>
              </div>

              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-semibold text-purple-800 dark:text-purple-200 flex items-center gap-2 hover:text-purple-900 dark:hover:text-purple-100">
                  <Info className="h-4 w-4" />
                  PSI Formula & Details
                </summary>
                <div className="mt-3 pl-6 space-y-2 text-sm text-purple-700 dark:text-purple-200 bg-white dark:bg-slate-900/60 p-3 rounded border border-purple-200 dark:border-slate-700">
                  <div>
                    <div className="font-semibold mb-1">Formula:</div>
                    <div className="font-mono bg-purple-50 dark:bg-slate-800 px-2 py-1 rounded">
                      PSI = Σ[(Actual% - Expected%) × ln(Actual% / Expected%)]
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold mb-1">Where:</div>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      <li><strong>Expected%</strong> = percentage in each bin for training (reference) distribution</li>
                      <li><strong>Actual%</strong> = percentage in each bin for test (current) distribution</li>
                      <li>The sum is over all quantile bins (typically 10)</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold mb-1">Interpretation:</div>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      <li><strong>PSI &lt; 0.1:</strong> No significant shift - model is stable</li>
                      <li><strong>0.1 ≤ PSI &lt; 0.25:</strong> Moderate shift - monitor closely</li>
                      <li><strong>PSI ≥ 0.25:</strong> Significant shift - investigate population changes</li>
                    </ul>
                  </div>
                </div>
              </details>
            </div>
          )}

          {/* CSI Section */}
          <div className="border border-blue-200 dark:border-slate-700 rounded-lg p-5 bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-slate-900 dark:to-slate-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-blue-600" />
                <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-200">Characteristic Stability Index (CSI)</h3>
              </div>
              <div className="text-sm text-blue-700 dark:text-blue-300">
                {sortedCSI.length} variable{sortedCSI.length !== 1 ? 's' : ''} analyzed
              </div>
            </div>

            {sortedCSI.length === 0 ? (
              <div className="text-center py-8 text-gray-600 dark:text-gray-300 bg-white dark:bg-slate-900/60 rounded-lg border border-blue-200 dark:border-slate-700">
                No CSI data available. CSI requires training and test feature data.
              </div>
            ) : (
              <>
                <div className="mb-4 bg-white dark:bg-slate-900/60 rounded-lg p-3 border border-blue-200 dark:border-slate-700">
                  <details>
                    <summary className="cursor-pointer text-sm font-semibold text-blue-800 dark:text-blue-200 flex items-center gap-2 hover:text-blue-900 dark:hover:text-blue-100">
                      <Info className="h-4 w-4" />
                      CSI Formula & Details
                    </summary>
                    <div className="mt-3 pl-6 space-y-2 text-sm text-blue-700 dark:text-blue-300">
                      <div>
                        <div className="font-semibold mb-1">Formula:</div>
                        <div className="font-mono bg-blue-50 dark:bg-slate-800 px-2 py-1 rounded">
                          CSI = Σ[(Actual% - Expected%) × ln(Actual% / Expected%)]
                        </div>
                      </div>
                      <div>
                        <div className="font-semibold mb-1">Where:</div>
                        <ul className="list-disc list-inside space-y-1 ml-2">
                          <li><strong>Expected%</strong> = percentage in each bin for training feature distribution</li>
                          <li><strong>Actual%</strong> = percentage in each bin for test feature distribution</li>
                          <li>CSI uses the same formula as PSI but is calculated per variable/feature</li>
                        </ul>
                      </div>
                      <div>
                        <div className="font-semibold mb-1">Interpretation:</div>
                        <ul className="list-disc list-inside space-y-1 ml-2">
                          <li><strong>CSI &lt; 0.1:</strong> No significant shift - variable is stable</li>
                          <li><strong>0.1 ≤ CSI &lt; 0.25:</strong> Moderate shift - some change detected</li>
                          <li><strong>CSI ≥ 0.25:</strong> Significant shift - major change, investigate</li>
                        </ul>
                      </div>
                    </div>
                  </details>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-blue-100 dark:bg-slate-900">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-blue-900 dark:text-blue-200">Variable</th>
                        <th className="px-4 py-3 text-right font-semibold text-blue-900 dark:text-blue-200">CSI Value</th>
                        <th className="px-4 py-3 text-center font-semibold text-blue-900 dark:text-blue-200">Status</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-slate-900/60 divide-y divide-gray-100 dark:divide-slate-800">
                      {sortedCSI.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-slate-800">
                          <td className="px-4 py-3 text-gray-900 dark:text-gray-200 font-medium">{row.Variable}</td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300 text-right font-mono">{formatNum(row.CSI, 4)}</td>
                          <td className="px-4 py-3 text-center">
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(row.Status)}`}>
                              {row.Status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Summary Statistics */}
                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white dark:bg-slate-900/60 rounded-lg p-3 border border-blue-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Stable Variables</div>
                    <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-300">
                      {sortedCSI.filter((r) => r.Status === 'Stable').length}
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-900/60 rounded-lg p-3 border border-blue-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Moderate Shift</div>
                    <div className="text-2xl font-bold text-amber-600 dark:text-amber-300">
                      {sortedCSI.filter((r) => r.Status === 'Moderate').length}
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-900/60 rounded-lg p-3 border border-blue-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Significant Shift</div>
                    <div className="text-2xl font-bold text-red-600 dark:text-red-300">
                      {sortedCSI.filter((r) => r.Status === 'Significant').length}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-slate-700 p-4 bg-gray-50 dark:bg-slate-900/70 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-purple-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-purple-700 dark:hover:bg-[#333380] transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default PSICSIModal;

