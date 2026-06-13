import React, { useState, ReactNode, Suspense, lazy } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
  sectionNumber: number;
  sectionTitle: string;
  defaultExpanded?: boolean;
  children: ReactNode | (() => ReactNode) | (() => JSX.Element) | (() => React.ReactElement);
  lazyLoad?: boolean;
  onToggle?: (isExpanded: boolean) => void;
}

/**
 * CollapsibleSection component with lazy loading support
 * Only renders children when expanded
 */
const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  sectionNumber,
  sectionTitle,
  defaultExpanded = false,
  children,
  lazyLoad = true,
  onToggle,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [hasBeenExpanded, setHasBeenExpanded] = useState(defaultExpanded);

  const handleToggle = () => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);
    
    if (newExpanded && !hasBeenExpanded) {
      setHasBeenExpanded(true);
    }
    
    if (onToggle) {
      onToggle(newExpanded);
    }
  };

  const shouldRenderContent = lazyLoad ? (isExpanded && hasBeenExpanded) : true;
  const content = shouldRenderContent 
    ? (typeof children === 'function' ? children() : children)
    : null;

  return (
    <div className="space-y-4">
      {/* Section Heading with Collapse/Expand Button */}
      <div 
        className="bg-blue-100 rounded-lg px-4 py-3 border border-blue-200 cursor-pointer hover:bg-blue-200 transition-colors"
        onClick={handleToggle}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-gray-900">
            <span className="mr-2">{sectionNumber}.</span>
            {sectionTitle}
          </h3>
          <div className="flex items-center">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-gray-700" />
            ) : (
              <ChevronRight className="h-5 w-5 text-gray-700" />
            )}
          </div>
        </div>
      </div>

      {/* Section Content */}
      {isExpanded && (
        <div className="animate-fadeIn">
          {lazyLoad ? (
            <Suspense fallback={
              <div className="pl-6 py-8 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <span className="ml-3 text-gray-600">Loading section...</span>
              </div>
            }>
              {content}
            </Suspense>
          ) : (
            content
          )}
        </div>
      )}
    </div>
  );
};

export default CollapsibleSection;

