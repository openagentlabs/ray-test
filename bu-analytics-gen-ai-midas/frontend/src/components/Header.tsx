import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Menu, Bell, Search, ChevronDown, User, Settings, LogOut, Sun, Moon } from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';

interface HeaderProps {
  user: {
    name: string;
    role: string;
    avatar: string;
  };
  onToggleSidebar: () => void;
  sidebarCollapsed: boolean;
}

/**
 * Derive a compact display name from the user object.
 * Prefers `user.name` unless it looks like an email address,
 * in which case it falls back to `user.username` or the local part of the email.
 */
function getDisplayName(u: { name: string; email?: string; username?: string }): string {
  const name = u.name?.trim();
  // If name is missing or is an email address, derive something shorter
  if (!name || name.includes('@')) {
    if (u.username && !u.username.includes('@')) return u.username;
    // Fall back to local part of email
    const email = name || u.email || '';
    const local = email.split('@')[0] || 'User';
    // Capitalise first letter
    return local.charAt(0).toUpperCase() + local.slice(1);
  }
  return name;
}

const Header: React.FC<HeaderProps> = ({ user, onToggleSidebar, sidebarCollapsed }) => {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, isAuthenticated } = useUser();
  const displayName = getDisplayName(user as any);
  //const { models, selection, setChatModelId, lockedByEnv, isObjectivesStep } = useLlmSelection();
  const { theme, toggleTheme, isDark } = useTheme();
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const navItems = [
    { label: 'Home', path: '/' },
    { label: 'Analytics', path: '/dashboard' },
    { label: 'Insights Console', path: '/chat' },
  ];

  return (
    <header className={`fixed top-0 left-0 right-0 z-[60] bg-white/80 dark:bg-gray-900/80 backdrop-blur-lg border-b border-gray-200/20 dark:border-gray-700/30 shadow-sm transition-colors duration-300`}>
      <div className="flex items-center justify-between px-4 h-16">
        {/* Left Section */}
        <div className="flex items-center space-x-4">
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Menu className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          </button>
          
          <Link to="/" className="flex items-center">
            <div>
              <h1 className="text-lg font-bold leading-tight" style={{ color: '#FB4E0B' }}>EXLdecision.ai</h1>
              <p className="text-[10px] font-medium leading-tight tracking-wide text-[#005071]">Modeling and Intelligent Decisioning Agentic Solution</p>
            </div>
          </Link>
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-3">
          {/* Search */}
          {/* <div className="hidden sm:block relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search datasets..."
              className="pl-10 pr-4 py-2 w-64 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div> */}

          {/* Notifications */}
          {/* <div className="relative" ref={notificationsRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors relative"
            >
              <Bell className="h-5 w-5 text-gray-600" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-orange-500 rounded-full"></span>
            </button>
            
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-[100]">
                <div className="px-4 py-2 border-b border-gray-100">
                  <h3 className="font-semibold text-gray-900">Notifications</h3>
                </div>
                <div className="py-2">
                  <div className="px-4 py-3 hover:bg-gray-50 cursor-pointer">
                    <p className="text-sm font-medium text-gray-900">Model training completed</p>
                    <p className="text-xs text-gray-500">Risk assessment model - 2 minutes ago</p>
                  </div>
                  <div className="px-4 py-3 hover:bg-gray-50 cursor-pointer">
                    <p className="text-sm font-medium text-gray-900">Anomaly detected</p>
                    <p className="text-xs text-gray-500">Transaction patterns - 1 hour ago</p>
                  </div>
                </div>
              </div>
            )}
          </div> */}

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? (
              <Sun className="h-5 w-5 text-yellow-400" />
            ) : (
              <Moon className="h-5 w-5 text-gray-600" />
            )}
          </button>

          {/* User Menu / Login Button */}
          {isAuthenticated ? (
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center space-x-2 p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                {/* Removed user avatar image */}
                <div className="hidden sm:block text-left max-w-[140px]">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{displayName}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.role}</p>
                </div>
                <ChevronDown className="h-4 w-4 text-gray-400 dark:text-gray-500" />
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-[100]">
                  <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                    <p className="font-medium text-gray-900 dark:text-gray-100 truncate">{displayName}</p>
                    {(user as any).email && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate" title={(user as any).email}>{(user as any).email}</p>
                    )}
                    <p className="text-xs text-gray-400 dark:text-gray-500">{user.role}</p>
                  </div>
                  <a href="#" className="flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <User className="h-4 w-4 mr-3" />
                    Profile
                  </a>
                  <a href="#" className="flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <Settings className="h-4 w-4 mr-3" />
                    Settings
                  </a>
                  <hr className="my-1 dark:border-gray-700" />
                  <button
                    onClick={() => {
                      logout();
                      setShowUserMenu(false);
                      navigate('/');
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    <LogOut className="h-4 w-4 mr-3" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => {
                // For demo purposes, let's simulate a login by setting a default user
                const defaultUser = {
                  name: 'Mayank',
                  role: 'Senior Data Analyst',
                  avatar: 'https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?auto=compress&cs=tinysrgb&w=400',
                  email: 'mayank@company.com',
                  id: 'user_001'
                };
                // This would normally be handled by a login function
                localStorage.setItem('userData', JSON.stringify(defaultUser));
                window.location.reload(); // Simple way to refresh the app state
              }}
              className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-blue-500 to-teal-500 text-white rounded-lg hover:from-blue-600 hover:to-teal-600 transition-all duration-200"
            >
              <User className="h-4 w-4" />
              <span className="hidden sm:block">Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
