import React, { useRef, useState, useEffect } from 'react';
import { Paperclip, Send, Plus, Folder, FileText } from 'lucide-react';
import DataSourceModal from './DataSourceModal';

interface Props {
  onSend: (userText: string) => void;
  isTyping: boolean;
}

const InsightsChatInput: React.FC<Props> = ({ onSend, isTyping }) => {
  const [value, setValue] = useState('');
  const [showDataSourceModal, setShowDataSourceModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (value.trim()) {
      onSend(value);
      setValue('');
      // Focus back on textarea after sending with a longer delay
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 200);
    }
  };

  const handleAttach = () => {
    setShowDataSourceModal(true);
  };

  const handleModalClose = () => {
    setShowDataSourceModal(false);
    // Focus back on textarea when modal closes
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
  };

  // Focus on textarea when component mounts
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Focus on textarea when typing state changes (after AI response)
  useEffect(() => {
    if (!isTyping) {
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  }, [isTyping]);

  return (
    <>
      <div className="w-[95%] mx-auto flex items-end space-x-3 p-4 bg-white dark:bg-gray-900 rounded-b-2xl shadow-lg border-t border-gray-100 dark:border-gray-700">
        <button
          className="p-2 rounded hover:bg-blue-50 transition"
          onClick={handleAttach}
          title="Select data source"
        >
          <Paperclip className="h-5 w-5 text-blue-500" />
        </button>
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".pdf,.csv,.xlsx,.xls,.doc,.docx,.png,.jpg,.jpeg"
          onChange={handleAttach}
        />
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none border border-gray-200 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[40px] max-h-32 shadow-sm transition"
          rows={1}
          placeholder="Type your message..."
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey && !isTyping) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isTyping}
        />
        <button
          className="p-2 rounded bg-blue-600 hover:bg-blue-700 text-white transition flex items-center justify-center disabled:opacity-50"
          onClick={handleSend}
          title="Send"
          disabled={isTyping || !value.trim()}
        >
          <Send className="h-5 w-5" />
        </button>
        {/* Add to Project/Artifact */}
        <div className="relative group">
          <button className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition" title="Add to...">
            <Plus className="h-5 w-5 text-gray-500" />
          </button>
          <div className="absolute right-0 mt-2 w-40 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition">
            <button className="w-full flex items-center px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-gray-700">
              <Folder className="h-4 w-4 mr-2 text-blue-400" /> Add to Project
            </button>
            <button className="w-full flex items-center px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-gray-700">
              <FileText className="h-4 w-4 mr-2 text-green-400" /> Add to Artifact
            </button>
          </div>
        </div>
      </div>

      {/* Data Source Selection Modal */}
      {showDataSourceModal && (
        <DataSourceModal onClose={handleModalClose} />
      )}
    </>
  );
};

export default InsightsChatInput; 