import React, { useState } from 'react';
import { Edit, RefreshCw, User, Bot, FileText, Plus, X } from 'lucide-react';
import { ChatMessage } from '../pages/ChatInterface';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useReports } from '../contexts/ReportsContext';

interface Props {
  messages: ChatMessage[];
  editingId: number | null;
  editValue: string;
  isTyping: boolean;
  onEdit: (msg: ChatMessage) => void;
  onEditChange: (val: string) => void;
  onEditSave: () => void;
  onEditCancel: () => void;
  onRegenerate: (userMsgId: number) => void;
}

// Markdown rendering components
const markdownComponents = {
  h1: (props: any) => <h1 className="text-2xl font-bold mt-2 mb-2 text-gray-900" {...props} />,
  h2: (props: any) => <h2 className="text-xl font-semibold mt-2 mb-2 text-gray-900" {...props} />,
  h3: (props: any) => <h3 className="text-lg font-semibold mt-2 mb-2 text-gray-900" {...props} />,
  ul: (props: any) => <ul className="list-disc pl-6 space-y-1 mb-2" {...props} />,
  ol: (props: any) => <ol className="list-decimal pl-6 space-y-1 mb-2" {...props} />,
  li: (props: any) => <li className="mb-1" {...props} />,
  p: (props: any) => <p className="mb-3 leading-relaxed" {...props} />,
  a: (props: any) => <a className="text-blue-600 underline hover:text-blue-800" target="_blank" rel="noopener noreferrer" {...props} />,
  code: (props: any) => <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono text-pink-700" {...props} />,
  pre: (props: any) => <pre className="bg-gray-100 rounded p-3 overflow-x-auto mb-3" {...props} />,
  blockquote: (props: any) => <blockquote className="border-l-4 border-blue-400 pl-4 italic text-gray-700 bg-blue-50 my-2 py-1" {...props} />,
  table: (props: any) => <table className="min-w-full border border-gray-200 my-2" {...props} />,
  th: (props: any) => <th className="border px-2 py-1 bg-gray-100 text-left" {...props} />,
  td: (props: any) => <td className="border px-2 py-1" {...props} />,
};

const InsightsChatArea: React.FC<Props> = ({
  messages,
  editingId,
  editValue,
  isTyping,
  onEdit,
  onEditChange,
  onEditSave,
  onEditCancel,
  onRegenerate
}) => {
  const [showAddToReportModal, setShowAddToReportModal] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<number | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [showNewReportModal, setShowNewReportModal] = useState(false);
  const [newReportName, setNewReportName] = useState('');
  const { reports, addReport } = useReports();

  const handleAddToReport = (messageId: number) => {
    setSelectedMessageId(messageId);
    setShowAddToReportModal(true);
  };

  const handleSelectReport = (reportId: number) => {
    setSelectedReportId(reportId);
    // Here you would add the message content to the selected report
    const message = messages.find(m => m.id === selectedMessageId);
    if (message) {
      console.log(`Adding message "${message.content.substring(0, 50)}..." to report ${reportId}`);
      // In a real app, you'd make an API call to add the content to the report
    }
    setShowAddToReportModal(false);
    setSelectedMessageId(null);
    setSelectedReportId(null);
  };

  const handleCreateNewReport = () => {
    setShowNewReportModal(true);
    setShowAddToReportModal(false);
  };

  const handleCreateReport = () => {
    if (newReportName.trim()) {
      addReport(newReportName);
      
      // Add the message to the newly created report
      const message = messages.find(m => m.id === selectedMessageId);
      if (message) {
        console.log(`Adding message "${message.content.substring(0, 50)}..." to new report "${newReportName}"`);
      }
      
      setNewReportName('');
      setShowNewReportModal(false);
      setSelectedMessageId(null);
    }
  };

  return (
    <>
      <div className="flex-1 w-full pl-2 md:pl-8 pr-1 md:pr-4 py-6 bg-gradient-to-br from-white to-blue-50 dark:from-gray-900 dark:to-gray-800 rounded-xl shadow-inner">
        <div className="max-w-5xl mx-auto space-y-6">
          {messages.map((msg, idx) => (
            <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'} group`}>
              <div className={`flex items-end space-x-3 ${msg.type === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`rounded-full p-2 ${msg.type === 'user' ? 'bg-blue-100 dark:bg-[#292966]' : 'bg-green-100 dark:bg-green-900/40'}`}>
                  {msg.type === 'user' ? <User className="h-5 w-5 text-blue-500 dark:text-[#ccccff]" /> : <Bot className="h-5 w-5 text-green-500 dark:text-green-400" />}
                </div>
                <div className={`rounded-2xl px-4 py-3 shadow ${msg.type === 'user' ? 'bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] w-[95%] mr-0 ml-auto' : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-green-200 dark:border-gray-700 w-[90%] ml-0 mr-auto'} relative transition-all duration-200`}>
                  {editingId === msg.id ? (
                    <div className="flex flex-col">
                      <textarea
                        className="w-full rounded border border-blue-300 p-2 text-sm mb-2"
                        value={editValue}
                        onChange={e => onEditChange(e.target.value)}
                        rows={2}
                      />
                      <div className="flex space-x-2">
                        <button className="px-3 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-blue-700 dark:hover:bg-[#333380] text-xs" onClick={onEditSave}>Save</button>
                        <button className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-xs" onClick={onEditCancel}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {msg.type === 'ai' ? (
                        <div className="prose prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="whitespace-pre-line text-sm">{msg.content}</div>
                      )}
                      <div className="flex items-center justify-between mt-3">
                        <div className="text-xs text-gray-400">{msg.time}</div>
                        <div className="flex items-center space-x-2">
                          {msg.type === 'user' && (
                            <button className="opacity-0 group-hover:opacity-100 transition" onClick={() => onEdit(msg)} title="Edit">
                              <Edit className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                            </button>
                          )}
                          {msg.type === 'ai' && idx > 0 && messages[idx - 1].type === 'user' && (
                            <>
                              <button className="opacity-0 group-hover:opacity-100 transition" onClick={() => onRegenerate(messages[idx - 1].id)} title="Regenerate">
                                <RefreshCw className="h-4 w-4 text-green-400 hover:text-green-600" />
                              </button>
                              <button 
                                className="opacity-0 group-hover:opacity-100 transition flex items-center space-x-1 text-xs text-blue-600 hover:text-blue-800"
                                onClick={() => handleAddToReport(msg.id)}
                                title="Add to Report"
                              >
                                <FileText className="h-3 w-3" />
                                <span>Add to Report</span>
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="flex items-end space-x-3">
                <div className="rounded-full p-2 bg-green-100">
                  <Bot className="h-5 w-5 text-green-500 animate-bounce" />
                </div>
                <div className="rounded-2xl px-4 py-3 shadow bg-white text-gray-900 border border-green-200 relative transition-all duration-200 w-[90%] ml-0 mr-auto">
                  <span className="text-sm text-gray-500 animate-pulse">Thinking...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add to Report Modal */}
      {showAddToReportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Add to Report</h3>
              <button
                onClick={() => setShowAddToReportModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Report
                </label>
                {reports.length > 0 ? (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {reports.map((report) => (
                      <button
                        key={report.id}
                        onClick={() => handleSelectReport(report.id)}
                        className="w-full text-left p-3 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition"
                      >
                        <div className="flex items-center space-x-3">
                          <FileText className="h-4 w-4 text-purple-500" />
                          <div className="flex-1">
                            <div className="font-medium text-gray-900">{report.name}</div>
                            <div className="text-xs text-gray-500">Created: {report.createdAt}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-gray-500">
                    <FileText className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p className="text-sm">No reports available</p>
                    <p className="text-xs">Create a report first to add content</p>
                  </div>
                )}
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowAddToReportModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateNewReport}
                  className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition flex items-center space-x-2"
                >
                  <Plus className="h-4 w-4" />
                  <span>Create New Report</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create New Report Modal */}
      {showNewReportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Create New Report</h3>
              <button
                onClick={() => setShowNewReportModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Report Name
                </label>
                <input
                  type="text"
                  value={newReportName}
                  onChange={(e) => setNewReportName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition"
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

export default InsightsChatArea; 