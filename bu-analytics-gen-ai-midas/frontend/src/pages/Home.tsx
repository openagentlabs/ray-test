import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Brain, 
  MessageSquare, 
  BarChart3, 
  Upload,
  Database,
  Shield,
  Activity
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';

const Home: React.FC = () => {
  const { user } = useUser();

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Welcome Header */}
      <div className="bg-gradient-to-r from-blue-600 to-teal-600 rounded-xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">Welcome back, {user.name}! 👋</h1>
            <p className="text-blue-100">Here's what's happening with your analytics platform</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">24/7</div>
            <div className="text-blue-100 text-sm">Platform Active</div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { label: 'Active Models', icon: Brain },
          { label: 'Datasets', icon: Database },
          { label: 'API Calls', icon: Activity },
          { label: 'Alerts', icon: Shield }
        ].map((stat, index) => (
          <div key={index} className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">0</p>
              </div>
              <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-teal-500 rounded-lg flex items-center justify-center">
                <stat.icon className="h-6 w-6 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Recent Activity</h2>
            <p className="text-gray-600 dark:text-gray-400 text-sm">Latest platform activities and updates</p>
          </div>
          <div className="p-6">
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <Activity className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p>No recent activity</p>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Performance Metrics</h2>
            <p className="text-gray-600 dark:text-gray-400 text-sm">Key platform performance indicators</p>
          </div>
          <div className="p-6">
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p>No metrics available</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Quick Actions</h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">Common tasks and shortcuts</p>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { title: 'Upload Data', icon: Upload, path: '/data', color: 'from-blue-500 to-cyan-500' },
              { title: 'Chat with AI', icon: MessageSquare, path: '/chat', color: 'from-purple-500 to-pink-500' },
              { title: 'Build Model', icon: Brain, path: '/models', color: 'from-green-500 to-emerald-500' },
              { title: 'View Analytics', icon: BarChart3, path: '/dashboard', color: 'from-orange-500 to-red-500' }
            ].map((action, index) => (
              <Link
                key={index}
                to={action.path}
                className="group block p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md transition-all duration-300 text-center"
              >
                <div className={`w-12 h-12 bg-gradient-to-r ${action.color} rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-300 mx-auto`}>
                  <action.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{action.title}</h3>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">System Status</h3>
            <div className="w-3 h-3 bg-gray-300 rounded-full"></div>
          </div>
          <div className="space-y-3">
            {['API Services', 'Database', 'ML Engine'].map((service) => (
              <div key={service} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">{service}</span>
                <span className="text-sm text-gray-400 dark:text-gray-500">Offline</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Models</h3>
          <div className="text-center text-gray-500 dark:text-gray-400 py-4">
            <Brain className="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
            <p className="text-sm">No models</p>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Data Sources</h3>
          <div className="text-center text-gray-500 dark:text-gray-400 py-4">
            <Database className="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
            <p className="text-sm">No data sources</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home; 