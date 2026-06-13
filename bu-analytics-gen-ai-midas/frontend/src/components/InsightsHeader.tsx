import React from 'react';
import { ChevronDown, HelpCircle } from 'lucide-react';
import { GeminiModel } from '../services/geminiApi';

const models = [
  { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
];

const InsightsHeader: React.FC<{
  selectedModel: GeminiModel;
  onModelChange: (model: GeminiModel) => void;
}> = ({ selectedModel, onModelChange }) => {
  return (
    <header className="w-full h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 shadow flex items-center px-6 justify-between z-20">
      {/* Brand/Logo */}
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 bg-gradient-to-r from-blue-600 to-teal-400 rounded-lg flex items-center justify-center shadow">
          <span className="text-white text-xl font-bold">O</span>
        </div>
        <span className="text-xl font-bold text-gray-900 dark:text-white tracking-tight">Oro</span>
      </div>
      {/* Model Selector */}
      <div className="flex items-center space-x-6">
        <div className="relative">
          <select
            className="appearance-none border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 text-sm font-medium text-gray-800 dark:text-gray-200 bg-white dark:bg-gray-800 shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-8"
            value={selectedModel}
            onChange={e => onModelChange(e.target.value as GeminiModel)}
          >
            {models.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        </div>
        {/* Help/Learn More */}
        <a href="#" className="flex items-center text-blue-600 hover:text-blue-800 text-sm font-medium transition">
          <HelpCircle className="h-4 w-4 mr-1" />
          Learn More
        </a>
      </div>
    </header>
  );
};

export default InsightsHeader; 