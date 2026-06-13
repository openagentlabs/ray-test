import React, { useState } from 'react';
import { Plus, MoreVertical, Folder, FileText, User, LogOut, Upload, ChevronLeft, ChevronRight, Bookmark, Edit, Trash2, X } from 'lucide-react';
import { useChats } from '../contexts/ChatsContext';
import { useUser } from '../contexts/UserContext';

interface Project {
  id: number;
  name: string;
}

interface Artifact {
  id: number;
  name: string;
}

/**
 * Derive a compact display name — prefer a real name over an email address.
 */
function getDisplayName(u: { name: string; email?: string; username?: string }): string {
  const name = u.name?.trim();
  if (!name || name.includes('@')) {
    if (u.username && !u.username.includes('@')) return u.username;
    const email = name || u.email || '';
    const local = email.split('@')[0] || 'User';
    return local.charAt(0).toUpperCase() + local.slice(1);
  }
  return name;
}

const InsightsSidebar: React.FC = () => {
  const { user: ctxUser } = useUser();
  const user = {
    name: ctxUser?.name || 'User',
    email: ctxUser?.email,
    username: ctxUser?.username,
    plan: 'Pro',
    avatar: ctxUser?.avatar || `https://ui-avatars.com/api/?name=User&background=3b82f6&color=ffffff`,
  };
  const displayName = getDisplayName(user);
  const [collapsed, setCollapsed] = useState(false);
  const { chats, addChat, updateChat, deleteChat, bookmarkChat, setCurrentChatId, currentChatId } = useChats();
  const [projects, setProjects] = useState<Project[]>([
    { id: 1, name: 'Q2 Reporting' },
    { id: 2, name: 'Synthetic Data Demo' },
  ]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([
    { id: 1, name: 'loan_data.csv' },
    { id: 2, name: 'risk_report.pdf' },
  ]);
  
  // State for dropdowns and modals
  const [showChatOptions, setShowChatOptions] = useState<number | null>(null);
  const [showProjectOptions, setShowProjectOptions] = useState<number | null>(null);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameType, setRenameType] = useState<'chat' | 'project'>('chat');
  const [renameId, setRenameId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [newProjectName, setNewProjectName] = useState('');

  const handleNewChat = () => {
    addChat(`New Chat ${chats.length + 1}`);
    setCurrentChatId(null); // Clear current chat to start fresh
  };

  const handleChatSelect = (chatId: number) => {
    setCurrentChatId(chatId);
    setShowChatOptions(null); // Close any open dropdowns
  };

  const handleChatOption = (chatId: number, action: 'bookmark' | 'rename' | 'delete') => {
    switch (action) {
      case 'bookmark':
        bookmarkChat(chatId);
        break;
      case 'rename':
        setRenameType('chat');
        setRenameId(chatId);
        const chat = chats.find(c => c.id === chatId);
        setRenameValue(chat?.title || '');
        setShowRenameModal(true);
        break;
      case 'delete':
        deleteChat(chatId);
        break;
    }
    setShowChatOptions(null);
  };

  const handleProjectOption = (projectId: number, action: 'rename' | 'delete') => {
    switch (action) {
      case 'rename':
        setRenameType('project');
        setRenameId(projectId);
        const project = projects.find(p => p.id === projectId);
        setRenameValue(project?.name || '');
        setShowRenameModal(true);
        break;
      case 'delete':
        setProjects(prev => prev.filter(project => project.id !== projectId));
        break;
    }
    setShowProjectOptions(null);
  };

  const handleAddProject = () => {
    if (newProjectName.trim()) {
      const newProject: Project = {
        id: Date.now(),
        name: newProjectName.trim()
      };
      setProjects(prev => [...prev, newProject]);
      setNewProjectName('');
      setShowNewProjectModal(false);
    }
  };

  const handleRename = () => {
    if (renameValue.trim()) {
      if (renameType === 'chat') {
        updateChat(renameId!, { title: renameValue.trim() });
      } else {
        setProjects(prev => prev.map(project => 
          project.id === renameId ? { ...project, name: renameValue.trim() } : project
        ));
      }
      setRenameValue('');
      setShowRenameModal(false);
      setRenameId(null);
    }
  };

  const handleLogout = () => {
    // Handle logout logic
    console.log('Logging out...');
  };

  return (
    <>
      <aside className={`h-full bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 shadow-lg flex flex-col transition-all duration-300 ${collapsed ? 'w-20' : 'w-72'} min-w-[5rem]`}>
        {/* Collapse/Expand Button */}
        <div className="flex justify-end p-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded hover:bg-gray-100 transition"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        <div className="flex-1 flex flex-col overflow-y-auto">
          {/* New Chat Button */}
          <div className="p-4">
            <button
              onClick={handleNewChat}
              className="w-full bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg px-4 py-2 flex items-center justify-center space-x-2 hover:bg-blue-700 dark:hover:bg-[#333380] transition"
            >
              <Plus className="h-4 w-4" />
              {!collapsed && <span>New Chat</span>}
            </button>
          </div>

          {/* Recent Chats */}
          <div className="px-4 mb-6">
            <div className="flex items-center justify-between mb-3">
              <span className={`text-xs font-semibold text-gray-500 uppercase tracking-wide ${collapsed ? 'hidden' : ''}`}>
                Recent Chats
              </span>
            </div>
            <div className="space-y-1">
              {chats.map((chat) => (
                <div key={chat.id} className="group relative">
                  <div 
                    className={`flex items-center justify-between p-2 rounded transition cursor-pointer ${
                      currentChatId === chat.id 
                        ? 'bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700' 
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                    }`}
                    onClick={() => handleChatSelect(chat.id)}
                  >
                    <div className="flex items-center space-x-2 min-w-0 flex-1">
                      <FileText className={`h-4 w-4 text-blue-500 ${collapsed ? 'mx-auto' : ''}`} />
                      {!collapsed && (
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {chat.title}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">{chat.time}</div>
                        </div>
                      )}
                    </div>
                    {!collapsed && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowChatOptions(showChatOptions === chat.id ? null : chat.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 transition p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-800"
                      >
                        <MoreVertical className="h-3 w-3 text-gray-400 dark:text-gray-500" />
                      </button>
                    )}
                  </div>
                  
                  {/* Chat Options Dropdown */}
                  {showChatOptions === chat.id && !collapsed && (
                    <div className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 min-w-[120px]">
                      <button
                        onClick={() => handleChatOption(chat.id, 'bookmark')}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 dark:text-gray-200"
                      >
                        <Bookmark className="h-3 w-3" />
                        <span>{chat.isBookmarked ? 'Remove Bookmark' : 'Bookmark'}</span>
                      </button>
                      <button
                        onClick={() => handleChatOption(chat.id, 'rename')}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 dark:text-gray-200"
                      >
                        <Edit className="h-3 w-3" />
                        <span>Rename</span>
                      </button>
                      <button
                        onClick={() => handleChatOption(chat.id, 'delete')}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 text-red-600 dark:text-red-500"
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>Delete</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Projects */}
          <div className="px-4 mb-6">
            <div className="flex items-center justify-between mb-3">
              <span className={`text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide ${collapsed ? 'hidden' : ''}`}>
                Projects
              </span>
              {!collapsed && (
                <button
                  onClick={() => setShowNewProjectModal(true)}
                  className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition"
                >
                  <Plus className="h-3 w-3 text-gray-500 dark:text-gray-500" />
                </button>
              )}
            </div>
            <div className="space-y-1">
              {projects.map((project) => (
                <div key={project.id} className="group relative">
                  <div className="flex items-center justify-between p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer">
                    <div className="flex items-center space-x-2 min-w-0 flex-1">
                      <Folder className={`h-4 w-4 text-green-500 ${collapsed ? 'mx-auto' : ''}`} />
                      {!collapsed && (
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {project.name}
                          </div>
                        </div>
                      )}
                    </div>
                    {!collapsed && (
                      <button
                        onClick={() => setShowProjectOptions(showProjectOptions === project.id ? null : project.id)}
                        className="opacity-0 group-hover:opacity-100 transition p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-800"
                      >
                        <MoreVertical className="h-3 w-3 text-gray-400 dark:text-gray-500" />
                      </button>
                    )}
                  </div>
                  
                  {/* Project Options Dropdown */}
                  {showProjectOptions === project.id && !collapsed && (
                    <div className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 min-w-[120px]">
                      <button
                        onClick={() => handleProjectOption(project.id, 'rename')}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 dark:text-gray-200"
                      >
                        <Edit className="h-3 w-3" />
                        <span>Rename</span>
                      </button>
                      <button
                        onClick={() => handleProjectOption(project.id, 'delete')}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 text-red-600 dark:text-red-500"
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>Delete</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Artifacts */}
          <div className="px-4 mb-6">
            <div className="flex items-center justify-between mb-3">
              <span className={`text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide ${collapsed ? 'hidden' : ''}`}>
                Artifacts
              </span>
            </div>
            <div className="space-y-1">
              {artifacts.map((artifact) => (
                <div key={artifact.id} className="flex items-center p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer">
                  <FileText className={`h-4 w-4 text-purple-500 ${collapsed ? 'mx-auto' : ''}`} />
                  {!collapsed && (
                    <div className="ml-2 min-w-0 flex-1">
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {artifact.name}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Profile Area */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-3">
            <img
              src={user.avatar}
              alt={user.name}
              className="w-8 h-8 rounded-full"
            />
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {displayName}
                </div>
                {user.email && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate" title={user.email}>{user.email}</div>
                )}
              </div>
            )}
            {!collapsed && (
              <button
                onClick={handleLogout}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition"
                title="Logout"
              >
                <LogOut className="h-4 w-4 text-gray-500 dark:text-gray-500" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* New Project Modal */}
      {showNewProjectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Create New Project</h3>
              <button
                onClick={() => setShowNewProjectModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Project Name
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter project name"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleAddProject();
                    }
                  }}
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowNewProjectModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddProject}
                  className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition"
                >
                  Create Project
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {showRenameModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                Rename {renameType === 'chat' ? 'Chat' : 'Project'}
              </h3>
              <button
                onClick={() => setShowRenameModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {renameType === 'chat' ? 'Chat' : 'Project'} Name
                </label>
                <input
                  type="text"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={`Enter ${renameType} name`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleRename();
                    }
                  }}
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowRenameModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRename}
                  className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition"
                >
                  Rename
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default InsightsSidebar; 