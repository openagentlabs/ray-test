import React from 'react';

type Option = {
  id: string;
  label: string;
  provider: string;
};

type LlmModelSelectProps = {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  disabled?: boolean;
  helpText?: string;
  size?: 'sm' | 'md';
};

const LlmModelSelect: React.FC<LlmModelSelectProps> = ({
  label,
  value,
  options,
  onChange,
  disabled = false,
  helpText,
  size = 'md',
}) => {
  const baseClass = size === 'sm'
    ? 'px-2 py-1 text-sm'
    : 'px-3 py-2 text-sm';

  return (
    <div className="space-y-1">
      <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wide">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`w-full border border-gray-300 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${baseClass} ${disabled ? 'bg-gray-100 dark:bg-slate-800 cursor-not-allowed text-gray-500 dark:text-gray-400' : 'bg-white dark:bg-slate-900 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-slate-800'}`}
      >
        {options.map(opt => (
          <option key={opt.id} value={opt.id} className="bg-white dark:bg-slate-900 text-gray-900 dark:text-white">
            {opt.label}
          </option>
        ))}
      </select>
      {helpText && (
        <p className="text-xs text-gray-500 dark:text-gray-400">{helpText}</p>
      )}
    </div>
  );
};

export default LlmModelSelect;


