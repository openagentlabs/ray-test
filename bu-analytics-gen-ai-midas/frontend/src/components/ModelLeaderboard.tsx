import React from 'react';
import { LeaderboardEntry } from '../services/fastApiService';

interface ModelLeaderboardProps {
  leaderboard: LeaderboardEntry[];
  problemType: string;
}

const ModelLeaderboard: React.FC<ModelLeaderboardProps> = ({ leaderboard, problemType }) => {
  if (!leaderboard || leaderboard.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No models trained yet
      </div>
    );
  }

  // Get primary metric for ranking
  const primaryMetric = problemType === 'classification' ? 'auc' : 'r2';

  // Get all available metrics from the first model
  const availableMetrics = Object.keys(leaderboard[0]?.metrics || {});

  const formatMetricValue = (value: number) => {
    return (value * 100).toFixed(2) + '%';
  };

  const getRankIcon = (rank: number) => {
    switch (rank) {
      case 1:
        return '🥇';
      case 2:
        return '🥈';
      case 3:
        return '🥉';
      default:
        return `#${rank}`;
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          Model Performance Leaderboard
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Ranked by {primaryMetric.toUpperCase()} • Problem Type: {problemType}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Rank
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Algorithm
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Model ID
              </th>
              {availableMetrics.map(metric => (
                <th key={metric} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {metric.toUpperCase()}
                </th>
              ))}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                CV Score
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {leaderboard.map((entry, index) => (
              <tr key={entry.model_id} className={index < 3 ? 'bg-yellow-50' : ''}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <span className="text-lg mr-2">
                      {getRankIcon(entry.rank)}
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {entry.rank}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">
                    {entry.algorithm}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    {entry.model_id}
                  </div>
                </td>
                {availableMetrics.map(metric => (
                  <td key={metric} className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">
                      {entry.metrics[metric] !== undefined ? (
                        metric === primaryMetric && entry.rank <= 3 ? (
                          <span className="font-semibold text-green-700">
                            {typeof entry.metrics[metric] === 'number' && entry.metrics[metric] < 1
                              ? formatMetricValue(entry.metrics[metric])
                              : entry.metrics[metric].toFixed(4)
                            }
                          </span>
                        ) : (
                          typeof entry.metrics[metric] === 'number' && entry.metrics[metric] < 1
                            ? formatMetricValue(entry.metrics[metric])
                            : entry.metrics[metric].toFixed(4)
                        )
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </div>
                  </td>
                ))}
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {entry.cv_scores && entry.cv_scores.length > 0
                      ? `${(entry.cv_scores.reduce((a, b) => a + b, 0) / entry.cv_scores.length * 100).toFixed(2)}%`
                      : '-'
                    }
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <button
                    className="text-indigo-600 hover:text-indigo-900 mr-3"
                    onClick={() => {
                      // Download model functionality
                      const link = document.createElement('a');
                      link.href = `/api/v1/models/${entry.model_id}/download-artifacts?format=pkl`;
                      link.download = `${entry.model_id}.pkl`;
                      link.click();
                    }}
                  >
                    Download
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          <p className="mb-2">
            <strong>Legend:</strong> Models are ranked by {primaryMetric.toUpperCase()}.
            Top 3 models are highlighted. All metrics are calculated on the test set.
          </p>
          <p>
            <strong>CV Score:</strong> Average cross-validation score across 5 folds.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ModelLeaderboard;
