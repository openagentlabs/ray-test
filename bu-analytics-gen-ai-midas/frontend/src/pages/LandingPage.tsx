import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Line, Bar, Doughnut, Radar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
);
import {
  Upload,
  MessageSquare,
  BarChart3,
  Brain,
  ArrowRight,
  Shield,
  Zap,
  Users,
  User,
  DatabaseZap,
  TrendingUp,
  Database,
  FlaskConical,
  FileText,
  CheckCircle,
  Play,
  Pause,
  RefreshCw,
  Eye,
  Download,
  Copy,
  CreditCard,
  Building,
  Globe,
  Sparkles,
  BarChart,
  PieChart,
  LineChart,
  Activity,
  Target,
  Award,
  Clock,
  Lock,
  Key,
  Cpu,
  Network,
  Cloud,
  Server,
  DollarSign,
  Calculator,
  TrendingDown,
  AlertTriangle,
  Scale,
  FileCheck,
  Monitor,
  Smartphone,
  Tablet,
  Wifi,
  Settings,
  HelpCircle,
  Info,
  Star,
  Heart,
  ThumbsUp,
  Trophy,
  Medal,
  Badge,
  GraduationCap,
  BookOpen,
  Lightbulb,
  Rocket,
  Bolt,
  Wind,
  Sun,
  Moon,
  CloudRain,
  CloudLightning,
  CloudSnow,
  CloudFog,
  CloudOff,
  CloudDrizzle,
  CloudHail,
  CloudRainWind
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import { LogIn, X } from 'lucide-react';
import AuthModal from '../components/AuthModal';
import cognitoAuthService from '../services/cognitoAuthService';
import { consumeSessionNotice } from '../services/sessionExpired';

const LandingPage: React.FC = () => {
  const { isAuthenticated, login } = useUser();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');
  const [activeFeature, setActiveFeature] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const [animatedStats, setAnimatedStats] = useState([0, 0, 0, 0]);
  const [currentUseCase, setCurrentUseCase] = useState(0);
  const [activeChart, setActiveChart] = useState(0);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const statsRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);

  const createAndStoreSessionId = (): string => {
    let id: string;
    try {
      if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
        id = (crypto as any).randomUUID();
      } else {
        id = 'sid_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
      }
    } catch {
      id = 'sid_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
    }
    sessionStorage.setItem('session_id', id);
    return id;
  };

  // Chart data
  const creditRiskData = {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    datasets: [
      {
        label: 'Credit Score Distribution',
        data: [720, 735, 748, 762, 778, 785],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true,
        yAxisID: 'y'
      },
      {
        label: 'Default Rate (%)',
        data: [2.1, 1.9, 1.7, 1.5, 1.3, 1.1],
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.4,
        fill: true,
        yAxisID: 'y1'
      }
    ]
  };

  const transactionData = {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [
      {
        label: 'Transaction Volume ($M)',
        data: [45, 52, 48, 61, 55, 38, 42],
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 2
      }
    ]
  };

  const portfolioData = {
    labels: ['Credit Cards', 'Mortgages', 'Personal Loans', 'Business Loans', 'Investments'],
    datasets: [
      {
        data: [35, 25, 15, 15, 10],
        backgroundColor: [
          'rgba(59, 130, 246, 0.8)',
          'rgba(16, 185, 129, 0.8)',
          'rgba(245, 158, 11, 0.8)',
          'rgba(239, 68, 68, 0.8)',
          'rgba(139, 92, 246, 0.8)'
        ],
        borderWidth: 2,
        borderColor: '#fff'
      }
    ]
  };

  const performanceData = {
    labels: ['Risk Score', 'Fraud Detection', 'Approval Rate', 'Customer Satisfaction', 'Compliance Score'],
    datasets: [
      {
        label: 'Current Performance',
        data: [85, 92, 78, 88, 95],
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 2,
        pointBackgroundColor: 'rgb(59, 130, 246)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(59, 130, 246)'
      },
      {
        label: 'Target Performance',
        data: [90, 95, 85, 92, 98],
        backgroundColor: 'rgba(16, 185, 129, 0.2)',
        borderColor: 'rgb(16, 185, 129)',
        borderWidth: 2,
        pointBackgroundColor: 'rgb(16, 185, 129)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(16, 185, 129)'
      }
    ]
  };

  useEffect(() => {
    const notice = consumeSessionNotice();
    if (notice) {
      setSessionNotice(notice);
      setShowAuthModal(true);
      setAuthModalMode('login');
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get('session') === 'expired') {
      setSessionNotice('Your session has expired. Please sign in again.');
      setShowAuthModal(true);
      setAuthModalMode('login');
      params.delete('session');
      const qs = params.toString();
      const path = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
      window.history.replaceState({}, '', path);
    }
  }, []);

  // Animation effects
  useEffect(() => {
    setIsVisible(true);

    // Animate stats when they come into view
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateStats();
          }
        });
      },
      { threshold: 0.5 }
    );

    if (statsRef.current) {
      observer.observe(statsRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const animateStats = () => {
    const targetStats = [99.9, 1, 10, 50];
    const duration = 2000;
    const steps = 60;
    const stepDuration = duration / steps;

    let currentStep = 0;
    const interval = setInterval(() => {
      currentStep++;
      const progress = currentStep / steps;

      setAnimatedStats(targetStats.map((target, index) => {
        if (index === 0) return Math.min(99.9, target * progress);
        if (index === 1) return progress >= 1 ? 1 : 0;
        return Math.floor(target * progress);
      }));

      if (currentStep >= steps) {
        clearInterval(interval);
      }
    }, stepDuration);
  };

  const handleAuthSuccess = (userData: any) => {
    login(userData);
    createAndStoreSessionId();
  };

  const handleShowLogin = () => {
    // Kick off the Cognito (Hosted UI + Entra ID) Authorization Code + PKCE flow.
    // The modal is retained only as a fallback UI for session-expired notices;
    // direct login goes straight to Cognito without a modal round-trip.
    cognitoAuthService.beginLogin().catch((e) => {
      console.error('Failed to start Cognito login:', e);
      // Fall back to the modal so the user still sees feedback.
      setAuthModalMode('login');
      setShowAuthModal(true);
    });
  };

  const scrollToTop = () => {
    if (topRef.current) {
      topRef.current.scrollIntoView({ behavior: 'smooth' });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const heroFeatures = [
    {
      icon: DatabaseZap,
      title: 'Synthetic Data Studio',
      description: 'Generate realistic datasets for testing and development',
      color: 'from-purple-500 to-pink-500'
    },
    {
      icon: MessageSquare,
      title: 'Insights Console',
      description: 'Chat with your data using AI-powered natural language queries',
      color: 'from-blue-500 to-teal-500'
    },
    {
      icon: Brain,
      title: 'Model Lab',
      description: 'Build, train, and deploy machine learning models for credit risk',
      color: 'from-green-500 to-emerald-500'
    },
    {
      icon: BarChart3,
      title: 'Advanced Analytics',
      description: 'Real-time dashboards with interactive visualizations and insights',
      color: 'from-orange-500 to-red-500'
    }
  ];

  const bankingUseCases = [
    {
      icon: CreditCard,
      title: 'Credit Card Risk Management',
      description: 'Monitor transaction patterns, detect fraud, and assess credit limits in real-time',
      features: ['Fraud Detection', 'Credit Limit Optimization', 'Transaction Monitoring', 'Risk Scoring'],
      color: 'from-red-500 to-pink-500',
      animation: 'bounce'
    },
    {
      icon: Building,
      title: 'Commercial Lending',
      description: 'Analyze business financials, assess creditworthiness, and manage loan portfolios',
      features: ['Financial Statement Analysis', 'Cash Flow Modeling', 'Industry Benchmarking', 'Portfolio Management'],
      color: 'from-blue-500 to-indigo-500',
      animation: 'pulse'
    },
    {
      icon: DollarSign,
      title: 'Mortgage Analytics',
      description: 'Evaluate mortgage applications, predict defaults, and optimize lending strategies',
      features: ['Application Scoring', 'Default Prediction', 'Market Analysis', 'Rate Optimization'],
      color: 'from-green-500 to-emerald-500',
      animation: 'spin'
    },
    {
      icon: Calculator,
      title: 'Personal Loan Assessment',
      description: 'Streamline personal loan processing with AI-powered credit evaluation',
      features: ['Income Verification', 'Debt-to-Income Analysis', 'Credit History Review', 'Automated Approval'],
      color: 'from-purple-500 to-violet-500',
      animation: 'wiggle'
    },
    {
      icon: TrendingUp,
      title: 'Investment Portfolio Management',
      description: 'Optimize investment strategies and manage risk across diverse portfolios',
      features: ['Portfolio Optimization', 'Risk Assessment', 'Performance Tracking', 'Asset Allocation'],
      color: 'from-yellow-500 to-orange-500',
      animation: 'slide'
    },
    {
      icon: Shield,
      title: 'Regulatory Compliance',
      description: 'Ensure compliance with BASEL III, IFRS 9, CECL, and other banking regulations',
      features: ['Model Governance', 'Audit Trails', 'Regulatory Reporting', 'Compliance Monitoring'],
      color: 'from-gray-500 to-slate-500',
      animation: 'fade'
    }
  ];

  const platformFeatures = [
    {
      category: 'Data Integration',
      features: [
        {
          icon: Upload,
          title: 'Multi-Source Data Ingestion',
          description: 'Upload CSV/Excel files, connect to SQL databases, Snowflake, AWS S3, and Azure Blob storage',
          highlights: ['Drag & Drop Upload', 'Real-time Validation', 'Schema Detection', 'Column Stats'],
          animation: 'slideInLeft'
        },
        {
          icon: Database,
          title: 'API Integrations',
          description: 'Connect to FRED economic data, FMP financial data, and custom APIs',
          highlights: ['FRED Economic Data', 'FMP Market Data', 'Real-time Feeds', 'Custom APIs'],
          animation: 'slideInRight'
        }
      ]
    },
    {
      category: 'AI & Analytics',
      features: [
        {
          icon: MessageSquare,
          title: 'Conversational AI',
          description: 'Ask questions in natural language and get instant insights, charts, and explanations',
          highlights: ['Natural Language Queries', 'Multi-Model AI', 'Real-time Responses', 'Context Awareness'],
          animation: 'fadeInUp'
        },
        {
          icon: Brain,
          title: 'Machine Learning Pipeline',
          description: 'End-to-end ML workflow from data preprocessing to model deployment',
          highlights: ['Auto Feature Engineering', 'Model Explainability', 'A/B Testing', 'Performance Monitoring'],
          animation: 'fadeInDown'
        }
      ]
    },
    {
      category: 'Industry Specialization',
      features: [
        {
          icon: CreditCard,
          title: 'Credit Risk Modeling',
          description: 'Specialized tools for credit scoring, default prediction, and risk assessment',
          highlights: ['Credit Scoring', 'Default Prediction', 'Risk Assessment', 'Regulatory Compliance'],
          animation: 'zoomIn'
        },
        {
          icon: DatabaseZap,
          title: 'Synthetic Data Generation',
          description: 'Create realistic banking datasets for testing without compromising real data',
          highlights: ['Credit Card Data', 'Mortgage Applications', 'Loan Portfolios', 'Transaction Patterns'],
          animation: 'rotateIn'
        }
      ]
    }
  ];

  const benefits = [
    {
      icon: Shield,
      title: 'Bank-Grade Security',
      description: 'End-to-end encryption, SOC 2 compliance, and comprehensive audit trails',
      features: ['AES-256 Encryption', 'Role-Based Access', 'Audit Logging', 'GDPR Compliance']
    },
    {
      icon: Zap,
      title: 'Real-Time Processing',
      description: 'Process millions of transactions and generate insights in seconds, not hours',
      features: ['Sub-second Queries', 'Live Data Streaming', 'Auto-scaling', '99.9% Uptime']
    },
    {
      icon: Users,
      title: 'Team Collaboration',
      description: 'Share insights, collaborate on models, and maintain version control across teams',
      features: ['Shared Workspaces', 'Version Control', 'Comment System', 'Approval Workflows']
    },
    {
      icon: Target,
      title: 'Regulatory Compliance',
      description: 'Built-in compliance frameworks for BASEL III, IFRS 9, CECL, and more',
      features: ['Model Governance', 'Explainability Reports', 'Bias Testing', 'Audit Trails']
    }
  ];

  const stats = [
    { number: '99.9%', label: 'Uptime' },
    { number: '<1s', label: 'Query Response' },
    { number: '10M+', label: 'Records Processed' },
    { number: '50+', label: 'ML Models Deployed' }
  ];

  const testimonials = [
    {
      name: 'Sarah Chen',
      role: 'Head of Risk Analytics',
      company: 'Global Bank',
      content: 'The synthetic data generation feature alone saved us 6 months of development time. The AI insights are incredibly accurate.',
      avatar: 'https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?auto=compress&cs=tinysrgb&w=400'
    },
    {
      name: 'Michael Rodriguez',
      role: 'Data Science Lead',
      company: 'FinTech Startup',
      content: 'The conversational AI interface makes complex analytics accessible to our entire team. Game-changing for our workflow.',
      avatar: 'https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=400'
    }
  ];

  return (
    <div className="h-screen overflow-y-auto">
      {/* Top reference for scrolling */}
      <div ref={topRef} className="absolute top-0" />

      {/* Navigation Header */}
      <nav className="bg-gradient-to-r from-slate-900/95 via-slate-800/95 to-slate-900/95 backdrop-blur-xl text-white px-6 py-4 fixed top-0 left-0 right-0 z-50 border-b border-slate-600/30 shadow-2xl">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Left Section - Branding */}
          <div
            className="flex items-center space-x-3 group cursor-pointer"
            onClick={scrollToTop}
          >
            <div className="flex flex-col">
              <span className="text-xl font-bold transition-all duration-300" style={{ color: '#FB4E0B' }}>EXLdecision.ai</span>
              <span className="text-xs font-medium tracking-wide text-[#005071] dark:text-[#dcf3fa]">Modeling and Intelligent Decisioning Agentic Solution</span>
            </div>
          </div>
          

          {/* Right Section - Auth Buttons */}

          <div className="flex items-center space-x-4">
            {!isAuthenticated ? (
              <button
                onClick={handleShowLogin}
                className="relative px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl border border-blue-400/30 hover:border-blue-300/50 transition-all duration-300 font-semibold shadow-lg hover:shadow-xl hover:shadow-blue-500/25 hover:scale-105 group overflow-hidden"
              >
                <span className="relative z-10 flex items-center space-x-2">
                  <LogIn className="h-4 w-4 group-hover:translate-x-1 transition-transform duration-300" />
                  <span>Sign In</span>
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-blue-400/20 to-blue-300/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              </button>
            ) : (
              <div className="flex items-center space-x-3">
                <div className="text-sm text-blue-100">
                  Welcome, {user?.name}!
                </div>
                <button
                  onClick={() => window.location.reload()}
                  className="relative px-6 py-2 bg-white/10 border border-white/30 text-white rounded-lg hover:bg-white/20 transition-all duration-300 font-medium"
                >
                  Dashboard
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {sessionNotice && (
        <div
          className="fixed top-[72px] left-0 right-0 z-40 px-4 py-3 bg-amber-50 dark:bg-amber-950/90 border-b border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-100 text-sm flex items-center justify-between gap-4 shadow-md"
          role="alert"
        >
          <span className="max-w-5xl mx-auto text-center flex-1">{sessionNotice}</span>
          <button
            type="button"
            onClick={() => setSessionNotice(null)}
            className="shrink-0 p-1 rounded hover:bg-amber-200/50 dark:hover:bg-amber-800/50"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-blue-900 via-blue-800 to-teal-700 text-white overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width=%2260%22%20height=%2260%22%20viewBox=%220%200%2060%2060%22%20xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cg%20fill=%22none%22%20fill-rule=%22evenodd%22%3E%3Cg%20fill=%22%23ffffff%22%20fill-opacity=%220.05%22%3E%3Ccircle%20cx=%2230%22%20cy=%2230%22%20r=%222%22/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')] opacity-30 animate-pulse"></div>

        <div className="relative max-w-7xl mx-auto px-4 py-32 lg:py-40">
          <div className="text-center">
            <div className="inline-flex items-center px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-6 animate-bounce">
              <Sparkles className="h-4 w-4 mr-2 animate-pulse" />
              🚀 AI-Powered Analytics Platform
            </div>

            <h1 className="text-4xl lg:text-6xl font-bold mb-6 leading-tight animate-fadeInUp" style={{ animationDelay: '0.5s', animationFillMode: 'forwards' }}>
              Transform Your Data into
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-teal-300 to-blue-300 pb-2 leading-relaxed">
                Actionable Intelligence
              </span>
            </h1>

            <p className="text-xl lg:text-2xl text-blue-100 mb-8 max-w-4xl mx-auto leading-relaxed animate-fadeInUp" style={{ animationDelay: '0.8s', animationFillMode: 'forwards' }}>
              The most comprehensive analytics platform with AI-powered insights, synthetic data generation,
              and advanced modeling capabilities designed for modern businesses.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12 animate-fadeInUp" style={{ animationDelay: '1.1s', animationFillMode: 'forwards' }}>
              {isAuthenticated ? (
                <>
                  <Link
                    to="/synthetic-data"
                    className="inline-flex items-center px-8 py-4 bg-white text-blue-900 font-semibold rounded-lg hover:bg-blue-50 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                  >
                    Try Synthetic Data Studio
                    <DatabaseZap className="ml-2 h-5 w-5" />
                  </Link>

                  <Link
                    to="/chat"
                    className="inline-flex items-center px-8 py-4 bg-teal-500 text-white font-semibold rounded-lg hover:bg-teal-600 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                  >
                    Explore Insights Console
                    <MessageSquare className="ml-2 h-5 w-5" />
                  </Link>

                  <Link
                    to="/models"
                    className="inline-flex items-center px-8 py-4 border-2 border-white text-white font-semibold rounded-lg hover:bg-white hover:text-blue-900 transition-all duration-200"
                  >
                    Visit Model Lab
                    <Brain className="ml-2 h-5 w-5" />
                  </Link>
                </>
              ) : (
                <>
                  <button
                    onClick={handleShowLogin}
                    className="inline-flex items-center px-8 py-4 bg-white text-blue-900 font-semibold rounded-lg hover:bg-blue-50 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                  >
                    Sign In to Start
                    <User className="ml-2 h-5 w-5" />
                  </button>


                </>
              )}
            </div>

            {/* Feature Preview Cards with Animations */}
          {/*  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-16">
              {heroFeatures.map((feature, index) => (
                <div
                  key={index}
                  className={`bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 hover:bg-white/20 transition-all duration-500 transform hover:scale-105 cursor-pointer ${activeFeature === index ? 'ring-2 ring-white/50' : ''
                    }`}
                  style={{
                    animationDelay: `${index * 0.2}s`,
                    animation: 'fadeInUp 0.8s ease-out forwards',
                    opacity: 0
                  }}
                  onClick={() => setActiveFeature(index)}
                >
                  <div className={`w-12 h-12 bg-gradient-to-r ${feature.color} rounded-lg flex items-center justify-center mb-4 hover:animate-pulse`}>
                    <feature.icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2 text-white">{feature.title}</h3>
                  <p className="text-blue-100 text-sm">{feature.description}</p>
                  <div className="mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <div className="w-full bg-white/20 rounded-full h-1">
                      <div className={`bg-gradient-to-r ${feature.color} h-1 rounded-full transition-all duration-1000`} style={{ width: activeFeature === index ? '100%' : '0%' }}></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            */}
          </div>
        </div>
      </section>
      

      {/* Ultimate CTA Section */}
    {/*  <section className="py-20 bg-gradient-to-br from-blue-900 via-purple-900 to-pink-900 text-white relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width=%2260%22%20height=%2260%22%20viewBox=%220%200%2060%2060%22%20xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cg%20fill=%22none%22%20fill-rule=%22evenodd%22%3E%3Cg%20fill=%22%23ffffff%22%20fill-opacity=%220.05%22%3E%3Ccircle%20cx=%2230%22%20cy=%2230%22%20r=%222%22/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')] opacity-30"></div>

        <div className="relative max-w-4xl mx-auto text-center px-4">
          <div className="mb-8">
            <div className="inline-flex items-center px-6 py-3 bg-white/10 backdrop-blur-sm rounded-full text-lg font-medium mb-6 animate-pulse">
              <Sparkles className="h-5 w-5 mr-2 animate-spin" />
              🚀 Ready to Revolutionize Business Analytics?
            </div>
          </div>

          <h2 className="text-4xl lg:text-6xl font-bold mb-6 animate-fadeInUp">
            Join the Future of
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 to-orange-500 animate-pulse">

            </span>
          </h2>

          <p className="text-xl text-purple-100 mb-8 max-w-3xl mx-auto">
            Experience the power of AI-driven insights, real-time processing, and predictive analytics that transform how businesses operate.
          </p>

          {/* Floating Features */}
        {/*  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            {[
              { icon: '⚡', feature: 'Real-time Processing', desc: 'Instant insights' },
              { icon: '🤖', feature: 'AI-Powered', desc: 'Smart analytics' },
              { icon: '🛡️', feature: 'Bank-Grade Security', desc: 'Enterprise ready' }
            ].map((item, index) => (
              <div key={index} className="bg-white/10 backdrop-blur-sm rounded-lg p-4 hover:bg-white/20 transition-all duration-300 transform hover:scale-105">
                <div className="text-3xl mb-2 animate-bounce">{item.icon}</div>
                <div className="font-semibold text-white">{item.feature}</div>
                <div className="text-sm text-purple-200">{item.desc}</div>
              </div>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            {isAuthenticated ? (
              <>
                <Link
                  to="/dashboard"
                  className="inline-flex items-center px-8 py-4 bg-white text-blue-900 font-semibold rounded-lg hover:bg-blue-50 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                >
                  Explore Dashboard
                  <BarChart3 className="ml-2 h-5 w-5" />
                </Link>
                <Link
                  to="/synthetic-data"
                  className="inline-flex items-center px-8 py-4 bg-teal-500 text-white font-semibold rounded-lg hover:bg-teal-600 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                >
                  Try Synthetic Data
                  <DatabaseZap className="ml-2 h-5 w-5" />
                </Link>
              </>
            ) : (
              <>
                <button
                  onClick={handleShowLogin}
                  className="inline-flex items-center px-8 py-4 bg-white text-blue-900 font-semibold rounded-lg hover:bg-blue-50 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105"
                >
                  Sign In to Start
                  <User className="ml-2 h-5 w-5" />
                </button>

              </>
            )}
          </div>
        </div>
      </section>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onLoginSuccess={handleAuthSuccess}
        initialMode={authModalMode}
      />
    </div>
  );
};

export default LandingPage;