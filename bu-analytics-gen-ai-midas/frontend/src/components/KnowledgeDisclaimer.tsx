import React from 'react';
import { Info } from 'lucide-react';

interface KnowledgeDisclaimerProps {
  sourceFiles?: string[];
  useExlExpertise?: boolean;
}

const KnowledgeDisclaimer: React.FC<KnowledgeDisclaimerProps> = ({
  sourceFiles = [],
  useExlExpertise = true
}) => {
  const renderSourceText = () => {
    const parts: string[] = [];

    if (sourceFiles.length > 0) {
      parts.push('your uploaded knowledge');
    }

    // useExlExpertise=True means we ARE using EXL expertise
    if (useExlExpertise) {
      parts.push('EXL Expertise');
    }

    return parts.length > 0 ? parts.join(' and ') : null;
  };

  const sourceText = renderSourceText();

  if (!sourceText) {
    return null;
  }

  return (
    <div className="mt-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg">
      <div className="flex items-start space-x-2">
        <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-blue-800 dark:text-blue-300">
          <span className="font-medium">Disclaimer:</span> This response is grounded and based on{' '}
          <span className="font-semibold">{sourceText}</span>.
        </p>
      </div>
    </div>
  );
};

export default KnowledgeDisclaimer;
