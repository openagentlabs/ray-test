import React, { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import LandingPage from './pages/LandingPage';
import Home from './pages/Home';
import DataIngestion from './pages/DataIngestion';
import ChatInterface from './pages/ChatInterface';
import Dashboard from './pages/Dashboard';
import Reports from './pages/Reports';
import APIDashboard from './pages/APIDashboard';
import SyntheticDataStudio from './pages/SyntheticDataStudio';

/** Code-split: ModelBuilder pulls in very large step components (e.g. Step6_5). Eager import blocked first paint on some machines. */
const ModelBuilder = lazy(() => import('./pages/ModelBuilder'));
const ModelEvaluationMEEA = lazy(() => import('./pages/ModelEvaluationMEEA'));
const ModelComparisonDashboard = lazy(() => import('./pages/ModelComparisonDashboard'));
import AuthCallback from './pages/AuthCallback';
import { DataProvider } from './contexts/DataContext';
import { DatabaseProvider } from './contexts/DatabaseContext';
import { UserProvider, useUser } from './contexts/UserContext';
import { ReportsProvider } from './contexts/ReportsContext';
import { ChatsProvider } from './contexts/ChatsContext';
import { DocumentationProvider } from './contexts/DocumentationContext';
import { ThemeProvider } from './contexts/ThemeContext';
import ProtectedRoute from './components/ProtectedRoute';
import SessionExpiredModal from './components/SessionExpiredModal';

function RouteLoadingFallback() {
  return (
    <div className="flex min-h-[40vh] w-full items-center justify-center">
      <div className="rounded-lg border border-slate-200 bg-white px-6 py-4 text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        Loading…
      </div>
    </div>
  );
}

function AppContent() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const { user, isAuthenticated } = useUser();

  // One-time cleanup of legacy LLM selection storage
  useEffect(() => {
    try {
      localStorage.removeItem('llm_selection');
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    // Clear all feature engineering related sessionStorage keys
    const featureEngineeringKeys = [
      'feature_engineering_selected_transformation',
      'feature_engineering_selected_variables', 
      'feature_engineering_applied_transformations',
      'feature_engineering_show_review',
      'feature_engineering_show_final_report',
      'feature_engineering_transformation_response',
      'feature_engineering_last_selected_variables',
      'feature_engineering_search_query'
    ];

    featureEngineeringKeys.forEach(key => {
      sessionStorage.removeItem(key);
    });

    console.log('🧹 Cleared feature engineering state on app startup');
  }, []); // Empty dependency array means this runs once on mount

  const handleSidebarToggle = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  const handleSidebarClose = () => {
    // Only close on mobile - on desktop, maintain collapsed state
    if (window.innerWidth < 1024) {
      setSidebarCollapsed(true);
    }
  };

  return (
    <DataProvider>
      <DatabaseProvider>
        <Router>
          <div className="h-screen flex flex-col">
            {isAuthenticated && user && (
              <div className="flex flex-col flex-1 bg-slate-50 dark:bg-gray-950 transition-colors duration-300">
                <Header 
                  user={user}
                  onToggleSidebar={handleSidebarToggle}
                  sidebarCollapsed={sidebarCollapsed}
                />
                
                <div className="flex flex-1 overflow-hidden mt-16">
                  <Sidebar 
                    collapsed={sidebarCollapsed}
                    onClose={handleSidebarClose}
                    className="lg:block"
                  />
                  
                  {/* Main content with proper responsive margins */}
                  <main className={`flex-1 transition-all duration-300 ease-in-out overflow-y-auto overflow-x-hidden ${
                    sidebarCollapsed 
                      ? 'lg:ml-16' // 64px for collapsed sidebar
                      : 'lg:ml-64' // 256px for expanded sidebar
                  } h-[calc(100vh-4rem)] pt-20 pb-6 px-4 lg:px-6`}>
                    <div className="max-w-full">
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <Routes>
                          <Route path="/" element={<Home />} />
                          <Route path="/data" element={
                            <ProtectedRoute>
                              <DataIngestion />
                            </ProtectedRoute>
                          } />
                          <Route path="/chat" element={
                            <ProtectedRoute>
                              <ChatInterface />
                            </ProtectedRoute>
                          } />
                          <Route path="/dashboard" element={
                            <ProtectedRoute>
                              <Dashboard />
                            </ProtectedRoute>
                          } />
                          <Route path="/api-dashboard" element={
                            <ProtectedRoute>
                              <APIDashboard />
                            </ProtectedRoute>
                          } />
                          <Route path="/models" element={
                            <ProtectedRoute>
                              <ModelBuilder />
                            </ProtectedRoute>
                          } />
                          <Route path="/synthetic-data" element={
                            <ProtectedRoute>
                              <SyntheticDataStudio />
                            </ProtectedRoute>
                          } />
                          <Route path="/reports" element={
                            <ProtectedRoute>
                              <Reports />
                            </ProtectedRoute>
                          } />
                          <Route path="/model-evaluation" element={
                            <ProtectedRoute>
                              <ModelEvaluationMEEA />
                            </ProtectedRoute>
                          } />
                          <Route path="/model-comparison" element={
                            <ProtectedRoute>
                              <ModelComparisonDashboard />
                            </ProtectedRoute>
                          } />
                        </Routes>
                      </Suspense>
                    </div>
                  </main>
                </div>
              </div>
            )}
            
            {!isAuthenticated && (
              <div className="flex-1 bg-white dark:bg-white">
                <Routes>
                  {/* Cognito Hosted UI redirects here after the user signs in via Entra.
                      Must be reachable before the app knows the user is authenticated. */}
                  <Route path="/auth/callback" element={<AuthCallback />} />
                  <Route path="/" element={<LandingPage />} />
                  <Route path="*" element={<LandingPage />} />
                </Routes>
              </div>
            )}
          </div>
        </Router>
      </DatabaseProvider>
    </DataProvider>
  );
}

function App() {
  return (
    <ThemeProvider>
      <UserProvider>
        <SessionExpiredModal />
        <ReportsProvider>
          <ChatsProvider>
            <DocumentationProvider>
                <AppContent />
            </DocumentationProvider>
          </ChatsProvider>
        </ReportsProvider>
      </UserProvider>
    </ThemeProvider>
  );
}

export default App;
