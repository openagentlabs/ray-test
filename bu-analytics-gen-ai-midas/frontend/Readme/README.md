# Banking Analytics Platform

A comprehensive financial analytics platform with AI-powered insights, real-time data integration, and advanced modeling capabilities.

## 🚀 Quick Start

1. **Clone the repository**
```bash
   git clone <repository-url>
   cd banking_analytics_v1-main
```

2. **Install dependencies**
```bash
npm install
```

3. **Configure Environment Variables**
   
   The application uses environment variables for secure API key management. Create a `.env` file in the project root (copy from `env.example`) with the following configuration:

   ```env
   # Google Gemini / Vertex AI
   VITE_GEMINI_API_KEY=your_gemini_api_key_here
   # Optional legacy key name supported by code for backward compatibility
   VITE_GOOGLE_CLOUD_API_KEY=your_google_cloud_api_key_here

   # Other API Keys (optional)
   VITE_FRED_API_KEY=your_fred_api_key_here
   VITE_FMP_API_KEY=your_fmp_api_key_here
   VITE_MOONSHOT_API_KEY=your_moonshot_api_key_here
   ```

   **🔒 Security Note**: The `.env` file is automatically ignored by Git to keep your API keys secure.

4. **Start the development server**
```bash
npm run dev
```

## 🤖 Vertex AI Integration

The platform now includes comprehensive Google Vertex AI integration:

- **Automatic Configuration**: Vertex AI is automatically configured using the `VITE_GOOGLE_CLOUD_API_KEY` from your `.env` file
- **Model Builder Integration**: AI assistance available in every step of the model building process
- **Chat Interface**: Gemini AI models available for conversational analytics
- **Real-time Status**: Persistent status indicator showing Vertex AI connection status

### Vertex AI Features:
- 🔍 **Data Analysis**: Automated data quality assessment and insights
- 🔧 **Feature Engineering**: AI-powered feature generation and optimization  
- 📊 **Model Analysis**: Deep model explainability and performance insights
- 🚀 **Deployment Guidance**: MLOps best practices and monitoring setup

## 🔑 API Key Management

### Google Cloud API Key Setup:
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create or select a project
3. Enable the Vertex AI API
4. Create an API key
5. The key is already configured in your `.env` file

### Security Best Practices:
- ✅ API keys are stored in `.env` file (not committed to Git)
- ✅ Environment variables are prefixed with `VITE_` for Vite compatibility
- ✅ Automatic service initialization on application startup
- ✅ Fallback handling for missing or invalid keys