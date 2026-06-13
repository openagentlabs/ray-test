import React, { useState, useRef, useEffect } from 'react';
import { MoreHorizontal, TrendingUp, TrendingDown, AlertTriangle, Users, DollarSign, Activity, Target, MessageSquare, Send, Plus, Sparkles, Download, Share2, Settings, Eye } from 'lucide-react';
import { useData } from '../contexts/DataContext';
import { geminiChatComplete, GeminiModel } from '../services/geminiApi';
import { generateSampleData, loadGoogleCharts, renderChart, createChartElement } from '../services/googleChartsService';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  hasVisualization?: boolean;
  visualizationType?: 'bar' | 'line' | 'pie' | 'table';
  chartData?: any;
}

const Dashboard: React.FC = () => {
  const { datasets, activeDataset } = useData();
  const [selectedTimeframe, setSelectedTimeframe] = useState('30d');
  const [showChat, setShowChat] = useState(false);
  const [visibleKpis, setVisibleKpis] = useState<number[]>([0, 1, 2, 3]);
  const [visibleCharts, setVisibleCharts] = useState<string[]>(['transactions', 'risk', 'segmentation', 'regional']);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: datasets.length > 0 
        ? 'Hi! I can help you create visualizations for your dashboard. What would you like to analyze?' 
        : 'Hi! I\'m your AI analytics assistant. To get started, please upload a dataset first. Once you have data, I can help you create charts and visualizations for your analytics.',
      timestamp: new Date(),
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<GeminiModel>('gemini-2.5-flash-lite');
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [googleChartsLoaded, setGoogleChartsLoaded] = useState(false);

  // Load Google Charts on component mount
  useEffect(() => {
    loadGoogleCharts()
      .then(() => {
        setGoogleChartsLoaded(true);
        console.log('Google Charts loaded successfully');
      })
      .catch((error) => {
        console.error('Failed to load Google Charts:', error);
      });
  }, []);

  // Auto-scroll to bottom when new messages are added or typing state changes
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages, isTyping]);

  const timeframes = [
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: '90d', label: '90 Days' },
    { value: '1y', label: '1 Year' },
  ];

  const kpiCards = [
    {
      title: 'Total Datasets',
      value: datasets.length.toString(),
      change: datasets.length > 0 ? 'Active' : 'No data',
      trend: datasets.length > 0 ? 'up' : 'neutral',
      icon: DollarSign,
      color: 'blue'
    },
    {
      title: 'Total Records',
      value: datasets.length > 0 ? datasets.reduce((sum, dataset) => sum + dataset.records, 0).toLocaleString() : '0',
      change: activeDataset ? `in ${activeDataset.name}` : 'No active dataset',
      trend: datasets.length > 0 ? 'up' : 'neutral',
      icon: Users,
      color: 'green'
    },
    {
      title: 'Data Treatment',
      value: datasets.length > 0 ? '95.2%' : 'N/A',
      change: datasets.length > 0 ? 'Good quality' : 'Upload data',
      trend: datasets.length > 0 ? 'up' : 'neutral',
      icon: AlertTriangle,
      color: 'orange'
    },
    {
      title: 'Active Dataset',
      value: activeDataset ? '1' : '0',
      change: activeDataset ? activeDataset.name.substring(0, 20) + '...' : 'Select dataset',
      trend: activeDataset ? 'up' : 'neutral',
      icon: Target,
      color: 'teal'
    }
  ];

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: chatInput,
      timestamp: new Date(),
    };

    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setIsTyping(true);

    try {
      // Only generate chart data if datasets are available
      let chartData = null;
      if (datasets.length > 0) {
        chartData = generateSampleData('auto', chatInput);
      }
      
      // Prepare context about the current data
      const dataContext = datasets.length > 0 
        ? `Current datasets: ${datasets.map(d => d.name).join(', ')}. Active dataset: ${activeDataset?.name || 'None'}. Timeframe: ${selectedTimeframe}.`
        : 'No datasets available.';

      // Create a concise prompt for the AI
      const prompt = datasets.length > 0 
        ? `You are an AI analytics assistant for a banking dashboard. ${dataContext}

User query: ${chatInput}

I've generated a ${chartData?.type} chart for this query. Provide a direct, concise response explaining the key insights from this visualization. Keep it brief and actionable.`
        : `You are an AI analytics assistant for a banking dashboard. ${dataContext}

User query: ${chatInput}

No datasets are currently available. Provide a helpful response explaining that data needs to be uploaded first, and suggest what kind of visualizations could be created once data is available.`;

      // Call Gemini API
      const aiResponse = await geminiChatComplete({
        prompt: prompt,
        model: selectedModel,
        history: chatMessages.map(m => ({ 
          role: m.type === 'user' ? 'user' : 'model', 
          parts: [m.content] 
        }))
      });

      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: aiResponse,
        timestamp: new Date(),
        hasVisualization: datasets.length > 0 && chartData !== null,
        visualizationType: chartData?.type as any,
        chartData: chartData,
      };
      
      setChatMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error calling Gemini API:', error);
      
      // Fallback response
      const fallbackMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'I apologize, but I encountered an error processing your request. Please try again or check your data sources.',
        timestamp: new Date(),
      };
      
      setChatMessages(prev => [...prev, fallbackMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const addVisualizationToDashboard = (messageId: string, type: string) => {
    // In a real app, this would add the visualization to the dashboard
    alert(`${type.charAt(0).toUpperCase() + type.slice(1)} chart added to dashboard!`);
  };

  const renderChartInMessage = (message: ChatMessage) => {
    if (!message.chartData || !googleChartsLoaded) return null;

    const chartId = `chart-${message.id}`;
    
    // Use setTimeout to ensure DOM is ready
    setTimeout(() => {
      const chartConfig = {
        type: message.chartData.type,
        data: message.chartData.data,
        options: message.chartData.options,
        elementId: chartId
      };
      
      renderChart(chartId, chartConfig);
    }, 100);

    return (
      <div className="mt-3 p-3 bg-blue-50 rounded border border-blue-200">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <Activity className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">
              {message.chartData.options.title}
            </span>
          </div>
          <button
            onClick={() => addVisualizationToDashboard(message.id, message.visualizationType!)}
            className="flex items-center space-x-1 px-3 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded text-xs hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
          >
            <Plus className="h-3 w-3" />
            <span>Add to Dashboard</span>
          </button>
        </div>
        <div id={chartId} className="w-full h-64"></div>
      </div>
    );
  };

  const removeKpi = (index: number) => {
    setVisibleKpis(prev => prev.filter(i => i !== index));
  };

  const removeChart = (chartId: string) => {
    setVisibleCharts(prev => prev.filter(id => id !== chartId));
  };

  const anomalies = [
    {
      id: 1,
      title: 'Unusual Transaction Pattern',
      description: 'Large transactions detected in Region 5',
      severity: 'high',
      timestamp: '2 hours ago',
      affected: '1,247 transactions'
    },
    {
      id: 2,
      title: 'Customer Behavior Drift',
      description: 'Spending patterns deviation in premium segment',
      severity: 'medium',
      timestamp: '6 hours ago',
      affected: '523 customers'
    },
    {
      id: 3,
      title: 'Model Performance Drop',
      description: 'Fraud detection accuracy below threshold',
      severity: 'high',
      timestamp: '1 day ago',
      affected: 'Model ID: FD-2024-01'
    }
  ];

  const exportChart = (chartId: string, format: 'png' | 'pdf' | 'csv') => {
    // In a real application, this would generate and download the chart
    alert(`Exporting ${chartId} chart as ${format.toUpperCase()}`);
    setActiveDropdown(null);
  };

  const shareChart = (chartId: string) => {
    // In a real application, this would generate a shareable link
    alert(`Generating shareable link for ${chartId} chart`);
    setActiveDropdown(null);
  };

  const configureChart = (chartId: string) => {
    // In a real application, this would open chart configuration
    alert(`Opening configuration for ${chartId} chart`);
    setActiveDropdown(null);
  };

  const renderSampleChart = (title: string, chartId: string, type: 'line' | 'bar' | 'doughnut' = 'line') => {
    // Show empty state when no datasets are available
    if (datasets.length === 0) {
      return (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden h-80">
          <div className="flex items-center justify-between p-4 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <div className="flex items-center space-x-2">
              <button 
                onClick={() => removeChart(chartId)}
                className="p-1 hover:bg-red-100 rounded text-red-500 hover:text-red-700 transition-colors"
                title="Remove chart"
              >
                ×
              </button>
              <div className="relative">
                <button 
                  className="p-1 hover:bg-gray-100 rounded transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveDropdown(activeDropdown === chartId ? null : chartId);
                  }}
                >
                  <MoreHorizontal className="h-4 w-4 text-gray-400" />
                </button>
                
                {activeDropdown === chartId && (
                  <div 
                    className="absolute right-0 top-8 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="px-3 py-2 border-b border-gray-100">
                      <p className="text-sm font-medium text-gray-900">Export Options</p>
                    </div>
                    
                    <button
                      onClick={() => exportChart(chartId, 'png')}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4 mr-3" />
                      Export as PNG
                    </button>
                    
                    <button
                      onClick={() => exportChart(chartId, 'pdf')}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4 mr-3" />
                      Export as PDF
                    </button>
                    
                    <button
                      onClick={() => exportChart(chartId, 'csv')}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4 mr-3" />
                      Export Data (CSV)
                    </button>
                    
                    <hr className="my-1" />
                    
                    <button
                      onClick={() => shareChart(chartId)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Share2 className="h-4 w-4 mr-3" />
                      Share Chart
                    </button>
                    
                    <button
                      onClick={() => configureChart(chartId)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Settings className="h-4 w-4 mr-3" />
                      Configure
                    </button>
                    
                    <button
                      onClick={() => alert(`Opening fullscreen view for ${chartId}`)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Eye className="h-4 w-4 mr-3" />
                      View Fullscreen
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="h-64 p-2">
            <div className="w-full h-full bg-gray-50 rounded-lg flex flex-col items-center justify-center border-2 border-dashed border-gray-300">
              <div className="text-center">
                <Plus className="h-8 w-8 text-gray-400 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Available</h3>
                <p className="text-gray-500 mb-4">Upload a dataset to start creating visualizations</p>
                <a 
                  href="/data" 
                  className="inline-flex items-center px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                >
                  Upload Data
                </a>
              </div>
            </div>
          </div>
        </div>
      );
    }

    // Show actual chart when data is available
    const renderActualChart = () => {
      if (type === 'line' && chartId === 'transactions') {
        return (
          <div className="w-full h-full bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-medium text-gray-700">Monthly Trend</span>
              <span className="text-sm text-green-600 font-semibold">↗ +12.3%</span>
            </div>
            <div className="flex-1 flex items-end justify-between px-2">
              {[42, 38, 45, 52, 48, 53].map((value, i) => (
                <div key={i} className="flex flex-col items-center space-y-2">
                  <div className="text-xs text-gray-600 font-medium">${value}M</div>
                  <div
                    className="w-6 bg-blue-500 rounded-t hover:bg-blue-600 transition-colors cursor-pointer"
                    style={{ height: `${(value / 60) * 120}px` }}
                  ></div>
                  <div className="text-xs text-gray-500">
                    {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'][i]}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      }
      
      if (type === 'doughnut' && chartId === 'risk') {
        return (
          <div className="w-full h-full bg-gradient-to-br from-green-50 to-red-50 rounded-lg p-4">
            <div className="grid grid-cols-2 gap-4 h-full">
              <div className="flex flex-col justify-center space-y-3">
                {[
                  { label: 'Low Risk', value: '65%', color: 'bg-green-500' },
                  { label: 'Medium', value: '25%', color: 'bg-yellow-500' },
                  { label: 'High Risk', value: '8%', color: 'bg-red-500' },
                  { label: 'Critical', value: '2%', color: 'bg-red-700' }
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={`w-3 h-3 rounded-full ${item.color}`}></div>
                      <span className="text-sm text-gray-700">{item.label}</span>
                    </div>
                    <span className="text-sm font-semibold text-gray-900">{item.value}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-center">
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600">65%</div>
                  <div className="text-sm text-gray-600">Low Risk</div>
                  <div className="text-xs text-gray-500 mt-1">158K customers</div>
                </div>
              </div>
            </div>
          </div>
        );
      }
      
      if (type === 'bar') {
        const isSegmentation = chartId === 'segmentation';
        const data = isSegmentation 
          ? [
              { label: 'Premium', value: 18, color: 'bg-purple-500' },
              { label: 'Standard', value: 65, color: 'bg-blue-500' },
              { label: 'Basic', value: 17, color: 'bg-green-500' }
            ]
          : [
              { label: 'North', value: 22, color: 'bg-blue-500' },
              { label: 'South', value: 15, color: 'bg-blue-500' },
              { label: 'East', value: 27, color: 'bg-blue-500' },
              { label: 'West', value: 17, color: 'bg-blue-500' },
              { label: 'Central', value: 19, color: 'bg-blue-500' }
            ];
        
        return (
          <div className="w-full h-full bg-gradient-to-br from-gray-50 to-blue-50 rounded-lg p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-medium text-gray-700">
                {isSegmentation ? 'Customer Segments' : 'Regional Revenue'}
              </span>
              <span className="text-sm text-blue-600 font-semibold">
                {isSegmentation ? '158K total' : '$57.4M'}
              </span>
            </div>
            <div className="flex-1 flex items-end justify-between px-2">
              {data.map((item, i) => (
                <div key={i} className="flex flex-col items-center space-y-2">
                  <div className="text-xs text-gray-600 font-medium">{item.value}%</div>
                  <div
                    className={`w-6 rounded-t ${item.color} hover:opacity-80 transition-opacity cursor-pointer`}
                    style={{ height: `${Math.max((item.value / 70) * 120, 12)}px` }}
                  ></div>
                  <div className="text-xs text-gray-500 text-center">
                    {item.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      }
      
      return (
        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-teal-50 rounded-lg p-4">
          <div className="text-center">
            <Activity className="h-8 w-8 text-blue-500 mx-auto mb-2" />
            <p className="text-sm text-gray-600">Interactive {type} Chart</p>
            <p className="text-xs text-gray-500">Real-time data visualization</p>
          </div>
        </div>
      );
    };

    return (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden h-80">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <div className="flex items-center space-x-2">
            <button 
              onClick={() => removeChart(chartId)}
              className="p-1 hover:bg-red-100 rounded text-red-500 hover:text-red-700 transition-colors"
              title="Remove chart"
            >
              ×
            </button>
            <div className="relative">
              <button 
                className="p-1 hover:bg-gray-100 rounded transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown(activeDropdown === chartId ? null : chartId);
                }}
              >
                <MoreHorizontal className="h-4 w-4 text-gray-400" />
              </button>
              
              {activeDropdown === chartId && (
                <div 
                  className="absolute right-0 top-8 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="px-3 py-2 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-900">Export Options</p>
                  </div>
                  
                  <button
                    onClick={() => exportChart(chartId, 'png')}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Download className="h-4 w-4 mr-3" />
                    Export as PNG
                  </button>
                  
                  <button
                    onClick={() => exportChart(chartId, 'pdf')}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Download className="h-4 w-4 mr-3" />
                    Export as PDF
                  </button>
                  
                  <button
                    onClick={() => exportChart(chartId, 'csv')}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Download className="h-4 w-4 mr-3" />
                    Export Data (CSV)
                  </button>
                  
                  <hr className="my-1" />
                  
                  <button
                    onClick={() => shareChart(chartId)}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Share2 className="h-4 w-4 mr-3" />
                    Share Chart
                  </button>
                  
                  <button
                    onClick={() => configureChart(chartId)}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Settings className="h-4 w-4 mr-3" />
                    Configure
                  </button>
                  
                  <button
                    onClick={() => alert(`Opening fullscreen view for ${chartId}`)}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Eye className="h-4 w-4 mr-3" />
                    View Fullscreen
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="h-64 p-2">
          {renderActualChart()}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 pt-6" onClick={() => setActiveDropdown(null)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
          <p className="text-gray-600 mt-1">Real-time insights from your data</p>
        </div>
        
        <div className="flex items-center space-x-3">
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            {timeframes.map((tf) => (
              <option key={tf.value} value={tf.value}>{tf.label}</option>
            ))}
          </select>
          
          <button
            onClick={() => setShowChat(!showChat)}
            className={`px-4 py-2 rounded-lg transition-colors flex items-center space-x-2 ${
              showChat 
                ? 'bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff]' 
                : 'border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            <span>Insights Console</span>
          </button>
          
          <button className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors">
            Export Report
          </button>
        </div>
      </div>

      {/* Chat Panel */}
      {showChat && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Insights Console</h2>
            <button
              onClick={() => setShowChat(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>
          
          <div 
            ref={chatContainerRef}
            className="h-64 overflow-y-auto mb-4 space-y-3 border border-gray-100 rounded-lg p-4"
          >
            {chatMessages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-md ${
                  message.type === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100'
                } rounded-lg p-3`}>
                  {message.type === 'assistant' && (
                    <div className="flex items-center space-x-2 mb-2">
                      <Sparkles className="h-3 w-3 text-blue-600" />
                      <span className="text-xs font-medium text-gray-600">AI Assistant</span>
                    </div>
                  )}
                  
                  <div className="whitespace-pre-wrap text-sm">{message.content}</div>
                  
                  {message.hasVisualization && message.chartData && renderChartInMessage(message)}
                  
                  <div className="text-xs opacity-70 mt-2">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg p-3">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="h-3 w-3 text-blue-600" />
                    <div className="flex space-x-1">
                      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Ask me to create a chart or analyze your data..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              onClick={(e) => e.stopPropagation()}
            />
            <button
              onClick={handleSendMessage}
              disabled={!chatInput.trim() || isTyping}
              className="p-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {kpiCards.map((kpi, index) => (
          visibleKpis.includes(index) && (
          <div key={index} className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                kpi.color === 'blue' ? 'bg-blue-100 text-blue-600' :
                kpi.color === 'green' ? 'bg-green-100 text-green-600' :
                kpi.color === 'orange' ? 'bg-orange-100 text-orange-600' :
                'bg-teal-100 text-teal-600'
              }`}>
                <kpi.icon className="h-5 w-5" />
              </div>
              
              <div className="flex items-center space-x-2">
                <button 
                  onClick={() => removeKpi(index)}
                  className="p-1 hover:bg-red-100 rounded text-red-500 hover:text-red-700 transition-colors text-sm"
                  title="Remove card"
                >
                  ×
                </button>
                <div className={`flex items-center space-x-1 text-sm ${
                kpi.trend === 'up' ? 'text-green-600' : 'text-red-600'
              }`}>
                  {kpi.trend === 'up' ? (
                    <TrendingUp className="h-4 w-4" />
                  ) : (
                    <TrendingDown className="h-4 w-4" />
                  )}
                  <span className="font-medium">{kpi.change}</span>
                </div>
              </div>
            </div>
            
            <div>
              <p className="text-2xl font-bold text-gray-900 mb-1">{kpi.value}</p>
              <p className="text-sm text-gray-600">{kpi.title}</p>
            </div>
          </div>
          )
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {visibleCharts.includes('transactions') && (
          <div className="lg:col-span-2">
            {renderSampleChart('Transaction Volume Over Time', 'transactions', 'line')}
          </div>
        )}
        {visibleCharts.includes('risk') && (
          <div>
            {renderSampleChart('Risk Distribution', 'risk', 'doughnut')}
          </div>
        )}
      </div>

      {/* Visualizations Container */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Visualizations</h2>
          <div className="flex items-center space-x-3">
            <button className="px-4 py-2 text-sm bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors">
              Add Chart
            </button>
            <button className="px-4 py-2 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
              Import
            </button>
          </div>
        </div>
        
        {datasets.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Sample Visualizations */}
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Revenue Trends</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-green-600 font-medium">+12.3%</span>
                  <TrendingUp className="h-3 w-3 text-green-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-blue-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-blue-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Line Chart</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Customer Segments</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-green-600 font-medium">158K</span>
                  <Users className="h-3 w-3 text-green-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-green-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-green-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Pie Chart</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Risk Distribution</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-purple-600 font-medium">65%</span>
                  <AlertTriangle className="h-3 w-3 text-purple-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-purple-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-purple-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Area Chart</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4 border border-orange-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Regional Performance</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-orange-600 font-medium">$57.4M</span>
                  <DollarSign className="h-3 w-3 text-orange-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-orange-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-orange-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Bar Chart</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-teal-50 to-teal-100 rounded-lg p-4 border border-teal-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Transaction Volume</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-teal-600 font-medium">1.2M</span>
                  <Activity className="h-3 w-3 text-teal-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-teal-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-teal-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Column Chart</p>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-pink-50 to-pink-100 rounded-lg p-4 border border-pink-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Credit Score vs Age</h3>
                <div className="flex items-center space-x-1">
                  <span className="text-xs text-pink-600 font-medium">0.78</span>
                  <Target className="h-3 w-3 text-pink-600" />
                </div>
              </div>
              <div className="h-32 bg-white rounded border border-pink-200 flex items-center justify-center">
                <div className="text-center">
                  <Activity className="h-6 w-6 text-pink-500 mx-auto mb-2" />
                  <p className="text-xs text-gray-600">Scatter Plot</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <Activity className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-gray-900 mb-2">No Visualizations Yet</h3>
            <p className="text-gray-500 mb-6 max-w-md mx-auto">
              Upload your data to start creating interactive visualizations and charts. 
              Our AI will help you generate insights and identify patterns in your data.
            </p>
            <div className="flex items-center justify-center space-x-4">
              <a 
                href="/data" 
                className="inline-flex items-center px-6 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
              >
                <Plus className="h-4 w-4 mr-2" />
                Upload Data
              </a>
              <button className="inline-flex items-center px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                <Sparkles className="h-4 w-4 mr-2" />
                View Examples
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;