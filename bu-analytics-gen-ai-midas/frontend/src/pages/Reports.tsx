import React, { useState } from 'react';
import { FileText, Download, Share2, Eye, Edit, Trash2, Plus, Calendar, Filter, Search } from 'lucide-react';

const Reports: React.FC = () => {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filterType, setFilterType] = useState('all');

  const reports = [
    {
      id: 1,
      title: 'Q4 Risk Assessment Report',
      description: 'Comprehensive analysis of risk factors and mitigation strategies',
      thumbnail: 'https://images.pexels.com/photos/590020/pexels-photo-590020.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'Sarah Mitchell',
      lastModified: '2 hours ago',
      type: 'risk',
      status: 'published',
      views: 247,
      shares: 15
    },
    {
      id: 2,
      title: 'Customer Segmentation Analysis',
      description: 'Detailed breakdown of customer demographics and behavior patterns',
      thumbnail: 'https://images.pexels.com/photos/669610/pexels-photo-669610.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'Michael Chen',
      lastModified: '1 day ago',
      type: 'analytics',
      status: 'draft',
      views: 89,
      shares: 3
    },
    {
      id: 3,
      title: 'Fraud Detection Model Performance',
      description: 'Monthly performance review of machine learning models',
      thumbnail: 'https://images.pexels.com/photos/590022/pexels-photo-590022.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'Lisa Rodriguez',
      lastModified: '3 days ago',
      type: 'model',
      status: 'published',
      views: 156,
      shares: 8
    },
    {
      id: 4,
      title: 'Regulatory Compliance Dashboard',
      description: 'Current compliance status and recommendations for improvement',
      thumbnail: 'https://images.pexels.com/photos/669612/pexels-photo-669612.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'David Park',
      lastModified: '1 week ago',
      type: 'compliance',
      status: 'published',
      views: 423,
      shares: 27
    },
    {
      id: 5,
      title: 'Market Bivariate Analysis',
      description: 'Analysis of current market conditions and their impact on banking operations',
      thumbnail: 'https://images.pexels.com/photos/590016/pexels-photo-590016.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'Emily Johnson',
      lastModified: '2 weeks ago',
      type: 'market',
      status: 'archived',
      views: 334,
      shares: 19
    },
    {
      id: 6,
      title: 'Transaction Volume Forecast',
      description: 'Predictive analysis for next quarter transaction volumes',
      thumbnail: 'https://images.pexels.com/photos/590018/pexels-photo-590018.jpeg?auto=compress&cs=tinysrgb&w=400',
      author: 'Robert Kim',
      lastModified: '3 weeks ago',
      type: 'forecast',
      status: 'published',
      views: 278,
      shares: 12
    }
  ];

  const getTypeColor = (type: string) => {
    const colors = {
      risk: 'bg-red-100 text-red-700',
      analytics: 'bg-blue-100 text-blue-700',
      model: 'bg-purple-100 text-purple-700',
      compliance: 'bg-green-100 text-green-700',
      market: 'bg-orange-100 text-orange-700',
      forecast: 'bg-teal-100 text-teal-700'
    };
    return colors[type as keyof typeof colors] || 'bg-gray-100 text-gray-700';
  };

  const getStatusColor = (status: string) => {
    const colors = {
      published: 'bg-green-100 text-green-700',
      draft: 'bg-yellow-100 text-yellow-700',
      archived: 'bg-gray-100 text-gray-700'
    };
    return colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-700';
  };

  const filteredReports = reports.filter(report => 
    filterType === 'all' || report.type === filterType
  );

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Reports & Analytics</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Create, share, and manage your analytics reports and insights.
          </p>
        </div>
        
        <button className="inline-flex items-center px-6 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] font-semibold rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors">
          <Plus className="h-5 w-5 mr-2" />
          New Report
        </button>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search reports..."
              className="pl-10 pr-4 py-2 w-64 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
          
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            <option value="all">All Types</option>
            <option value="risk">Risk</option>
            <option value="analytics">Analytics</option>
            <option value="model">Model</option>
            <option value="compliance">Compliance</option>
            <option value="market">Market</option>
            <option value="forecast">Forecast</option>
          </select>
        </div>

        <div className="flex items-center space-x-2">
          <button className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
            <Filter className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          </button>
          <button className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
            <Calendar className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          </button>
        </div>
      </div>

      {/* Reports Grid */}
      <div className="grid lg:grid-cols-3 md:grid-cols-2 gap-6">
        {filteredReports.map((report) => (
          <div key={report.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-lg transition-all duration-200 group">
            {/* Thumbnail */}
            <div className="relative h-40 bg-gray-100 dark:bg-gray-700 overflow-hidden">
              <img
                src={report.thumbnail}
                alt={report.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
              />
              <div className="absolute top-3 left-3 flex space-x-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(report.type)}`}>
                  {report.type}
                </span>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(report.status)}`}>
                  {report.status}
                </span>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2 line-clamp-2 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                {report.title}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                {report.description}
              </p>
              
              <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-4">
                <span>By {report.author}</span>
                <span>{report.lastModified}</span>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400">
                  <div className="flex items-center space-x-1">
                    <Eye className="h-3 w-3" />
                    <span>{report.views}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Share2 className="h-3 w-3" />
                    <span>{report.shares}</span>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors">
                    <Eye className="h-4 w-4 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400" />
                  </button>
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors">
                    <Edit className="h-4 w-4 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400" />
                  </button>
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors">
                    <Download className="h-4 w-4 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400" />
                  </button>
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors">
                    <Share2 className="h-4 w-4 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">Recent Activity</h2>
        <div className="space-y-4">
          {[
            {
              action: 'Report Published',
              details: 'Q4 Risk Assessment Report has been published',
              user: 'Sarah Mitchell',
              time: '2 hours ago',
              type: 'publish'
            },
            {
              action: 'Report Shared',
              details: 'Customer Segmentation Analysis shared with Risk Team',
              user: 'Michael Chen',
              time: '4 hours ago',
              type: 'share'
            },
            {
              action: 'Report Updated',
              details: 'Fraud Detection Model Performance updated with new metrics',
              user: 'Lisa Rodriguez',
              time: '1 day ago',
              type: 'edit'
            },
            {
              action: 'Report Created',
              details: 'New regulatory compliance report created',
              user: 'David Park',
              time: '2 days ago',
              type: 'create'
            }
          ].map((activity, index) => (
            <div key={index} className="flex items-start space-x-4 p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-lg transition-colors">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                activity.type === 'publish' ? 'bg-green-100 text-green-600' :
                activity.type === 'share' ? 'bg-blue-100 text-blue-600' :
                activity.type === 'edit' ? 'bg-orange-100 text-orange-600' :
                'bg-purple-100 text-purple-600'
              }`}>
                {activity.type === 'publish' ? <FileText className="h-4 w-4" /> :
                 activity.type === 'share' ? <Share2 className="h-4 w-4" /> :
                 activity.type === 'edit' ? <Edit className="h-4 w-4" /> :
                 <Plus className="h-4 w-4" />}
              </div>
              
              <div className="flex-1">
                <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">{activity.action}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">{activity.details}</p>
                <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
                  <span>{activity.user}</span>
                  <span>•</span>
                  <span>{activity.time}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gradient-to-br from-blue-50 to-teal-50 dark:from-blue-900/20 dark:to-teal-900/20 rounded-xl border border-blue-200 dark:border-blue-800 p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Quick Actions</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <button className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-gray-700 hover:shadow-md transition-all text-left">
            <FileText className="h-8 w-8 text-blue-600 dark:text-blue-400 mb-2" />
            <h3 className="font-medium text-gray-900 dark:text-white">Create Report</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Start a new analytics report</p>
          </button>
          
          <button className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-gray-700 hover:shadow-md transition-all text-left">
            <Download className="h-8 w-8 text-teal-600 dark:text-teal-400 mb-2" />
            <h3 className="font-medium text-gray-900 dark:text-white">Export Data</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Download reports as PDF/CSV</p>
          </button>
          
          <button className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-gray-700 hover:shadow-md transition-all text-left">
            <Share2 className="h-8 w-8 text-purple-600 dark:text-purple-400 mb-2" />
            <h3 className="font-medium text-gray-900 dark:text-white">Schedule Report</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Set up automated deliveries</p>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Reports;