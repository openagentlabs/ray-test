import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  Home, 
  Upload, 
  MessageSquare, 
  BarChart3, 
  Brain, 
  FileText, 
  Settings,
  HelpCircle,
  TrendingUp,
  Database,
  Building,
  DollarSign,
  FlaskConical,
  Sparkles,
  DatabaseZap
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';

interface SidebarProps {
  collapsed: boolean;
  className?: string;
  onClose?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ collapsed, className = '', onClose }) => {
  const location = useLocation();
  const { isAuthenticated } = useUser();

  const menuItems = [
    { icon: Home, label: 'Home', path: '/', badge: null },
    { icon: Brain, label: 'Model Lab', path: '/models', badge: null },
    // { icon: DatabaseZap, label: 'Synthetic Data Studio', path: '/synthetic-data', badge: 'NEW' },
    { icon: Upload, label: 'Data Sources', path: null, badge: null },
    { icon: MessageSquare, label: 'Insights Console', path: null, badge: '2' },
    { icon: BarChart3, label: 'Analytics', path: null, badge: null },
    { icon: Database, label: 'API Dashboard', path: null, badge: 'LIVE' },
    { icon: FileText, label: 'Reports', path: null, badge: null },
  ];

  const bottomItems = [
    { icon: TrendingUp, label: 'AI Insights', path: null },
    { icon: Settings, label: 'Settings', path: null },
    { icon: HelpCircle, label: 'Help & Support', path: null },
  ];

  const renderMenuItem = (item: any, index: number, isBottom = false) => {
    const isActive = location.pathname === item.path;
    const className = `flex items-center px-3 py-3 mx-2 rounded-lg transition-all duration-200 group relative ${
      isActive
        ? 'bg-gradient-to-r from-blue-50 to-teal-50 dark:from-blue-900/30 dark:to-teal-900/30 text-blue-700 dark:text-blue-400 border-r-2 border-blue-500'
        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-gray-200'
    }`;
    const key = item.path || `${isBottom ? 'bottom' : 'main'}-${item.label}-${index}`;
    const content = (
      <>
        <item.icon className={`h-5 w-5 ${collapsed ? 'mx-auto' : 'mr-3'} transition-colors duration-200`} />
        {!collapsed && (
          <>
            <span className="font-medium text-sm truncate">{item.label}</span>
            {item.badge && (
              <span className={`ml-auto px-2 py-1 text-xs rounded-full font-medium ${
                item.badge === 'LIVE'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : item.badge === 'NEW'
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                  : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
              }`}>
                {item.badge}
              </span>
            )}
          </>
        )}
      </>
    );

    if (!item.path) {
      return (
        <button
          key={key}
          type="button"
          className={className}
          onClick={onClose}
        >
          {content}
        </button>
      );
    }

    return (
      <Link
        key={key}
        to={item.path}
        onClick={onClose}
        className={className}
      >
        {content}
      </Link>
    );
  };

  return (
    <>
      {/* Mobile overlay */}
      {!collapsed && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}
      
      {/* Sidebar */}
      <aside className={`fixed left-0 top-16 h-[calc(100vh-4rem)] bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 shadow-sm transition-all duration-300 z-40 ${
        collapsed ? 'w-16' : 'w-64'
      } ${className} ${
        // On mobile, slide in from left when expanded
        !collapsed ? 'translate-x-0' : 'lg:translate-x-0 -translate-x-full lg:translate-x-0'
      }`}>
        <div className="flex flex-col h-full overflow-hidden">
          {/* Main Navigation */}
          <nav className="flex-1 pt-6 pb-4 overflow-y-auto">
            <div className="space-y-1">
              {isAuthenticated ? (
                menuItems.map((item, index) => renderMenuItem(item, index))
              ) : (
                // Show only Overview for unauthenticated users
                menuItems.filter(item => item.path === '/').map((item, index) => renderMenuItem(item, index))
              )}
            </div>
          </nav>

          {/* AI Insights Section */}
          {!collapsed && isAuthenticated && (
            <div className="px-4 py-4 border-t border-gray-100 dark:border-gray-700">
              <div className="bg-gradient-to-r from-blue-50 to-teal-50 dark:from-blue-900/20 dark:to-teal-900/20 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-teal-500 rounded-lg flex items-center justify-center flex-shrink-0">
                    <TrendingUp className="h-4 w-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI Recommendation</h4>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      Review anomaly patterns in Q4 transaction data
                    </p>
                    <button className="text-xs text-blue-600 dark:text-blue-400 font-medium mt-2 hover:text-blue-700 dark:hover:text-blue-300">
                      View Details →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Bottom Navigation */}
          {isAuthenticated && (
            <div className="border-t border-gray-100 dark:border-gray-700 py-4">
              <div className="space-y-1">
                {bottomItems.map((item, index) => renderMenuItem(item, index, true))}
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
