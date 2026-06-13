import React, { useRef, useState } from 'react';
import { Upload, FileText, Image, FolderPlus, X, Plus } from 'lucide-react';
import { useReports } from '../contexts/ReportsContext';

interface InsightsArtifactsPaneProps {
  onToggle: () => void;
}

const artifacts = [
  { id: 1, name: 'loan_data.csv', type: 'csv' },
  { id: 2, name: 'risk_report.pdf', type: 'pdf' },
  { id: 3, name: 'chart.png', type: 'image', url: 'https://placekitten.com/200/200' },
];

const InsightsArtifactsPane: React.FC<InsightsArtifactsPaneProps> = ({ onToggle }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showNewReportModal, setShowNewReportModal] = useState(false);
  const [newReportName, setNewReportName] = useState('');
  const { reports, addReport } = useReports();

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      alert('Uploaded: ' + e.target.files[0].name);
    }
  };

  const handleCreateReport = () => {
    if (newReportName.trim()) {
      addReport(newReportName);
      setNewReportName('');
      setShowNewReportModal(false);
    }
  };

  return (
    <>
      <aside className="w-full md:w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 shadow-lg flex flex-col p-4 space-y-4 min-h-[400px]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Artifacts</span>
          <div className="flex items-center space-x-2">
            <button
              className="p-1 rounded hover:bg-blue-50 transition"
              onClick={() => fileInputRef.current?.click()}
              title="Upload artifact"
            >
              <Upload className="h-4 w-4 text-blue-500" />
            </button>
            <button
              onClick={() => setShowNewReportModal(true)}
              className="p-1 rounded hover:bg-blue-50 transition"
              title="Create new report"
            >
              <Plus className="h-4 w-4 text-blue-500" />
            </button>
            <button
              onClick={onToggle}
              className="p-1 rounded hover:bg-gray-100 transition"
              title="Hide artifacts"
            >
              <X className="h-4 w-4 text-gray-500" />
            </button>
          </div>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".pdf,.csv,.xlsx,.xls,.doc,.docx,.png,.jpg,.jpeg"
            onChange={handleUpload}
          />
        </div>
        
        {/* Reports Section */}
        {reports.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Reports</div>
            <ul className="space-y-1">
              {reports.map((report) => (
                <li key={report.id} className="flex items-center space-x-2 p-2 rounded hover:bg-blue-50 dark:hover:bg-gray-800 transition cursor-pointer">
                  <FileText className="h-4 w-4 text-purple-500" />
                  <span className="truncate text-gray-800 dark:text-gray-200 text-sm flex-1">{report.name}</span>
                  <span className="text-xs text-gray-400">{report.createdAt}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        <ul className="space-y-2">
          {artifacts.map((file) => (
            <li key={file.id} className="flex items-center space-x-3 p-2 rounded hover:bg-blue-50 dark:hover:bg-gray-800 transition cursor-pointer">
              {file.type === 'image' ? (
                <Image className="h-5 w-5 text-green-400" />
              ) : (
                <FileText className="h-5 w-5 text-blue-400" />
              )}
              <span className="truncate text-gray-800 dark:text-gray-200 text-sm flex-1">{file.name}</span>
              <button className="p-1 rounded hover:bg-gray-100 transition" title="Add to Project">
                <FolderPlus className="h-4 w-4 text-blue-500" />
              </button>
            </li>
          ))}
        </ul>
        {/* Preview area */}
        <div className="mt-4">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Preview</div>
          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 min-h-[120px] flex items-center justify-center">
            {/* Placeholder preview */}
            <span className="text-gray-400 dark:text-gray-500 text-sm">Select an artifact to preview</span>
          </div>
        </div>
      </aside>

      {/* New Report Modal */}
      {showNewReportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Create New Report</h3>
              <button
                onClick={() => setShowNewReportModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Report Name
                </label>
                <input
                  type="text"
                  value={newReportName}
                  onChange={(e) => setNewReportName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter report name"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleCreateReport();
                    }
                  }}
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowNewReportModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateReport}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition"
                >
                  Create Report
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default InsightsArtifactsPane; 