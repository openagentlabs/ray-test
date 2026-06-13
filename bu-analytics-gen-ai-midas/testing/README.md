# MIDAS Comprehensive Testing Suite

This testing suite provides automated testing for all MIDAS platform features to ensure stability and catch regressions during development.

## Features Tested

### 🔄 Data Management & Ingestion
- Dataset upload and validation
- Problem type detection (classification/regression)
- Dataset configuration and metadata

### 🧹 Data Quality & Treatment  
- Missing value detection and treatment
- Outlier detection
- Duplicate detection
- Data validation

### 📊 Data Insights & Analysis
- Bivariate analysis
- Correlation analysis (Pearson, Spearman)
- VIF (Variance Inflation Factor) analysis
- Knowledge graph generation

### 🎯 Segmentation
- CART segmentation
- CHAID segmentation  
- Segment profiling
- Segmented data insights

### ⚙️ Feature Engineering
- WOE (Weight of Evidence) transformations
- Log transformations
- One-hot encoding
- Custom feature engineering pipelines

### 🤖 Model Training
- Global model training (XGBoost, Random Forest, Logistic Regression, etc.)
- Segment-level model training
- Hyperparameter optimization (Bayesian, Random Search)
- VIF-aware model training

### 📈 Model Evaluation (MEEA)
- Comprehensive performance metrics
- Feature importance analysis
- Granular accuracy analysis
- Error pattern detection

### 🔮 AI Explainability
- SHAP value calculations
- LIME explanations
- Partial dependence plots (PDP)
- Individual conditional expectation (ICE) plots
- Permutation importance

### 💬 Chat & AI Assistant
- Natural language dataset queries
- Code execution capabilities
- AI-powered data analysis

### 📚 Reporting & Documentation
- Model codebooks
- API documentation
- Performance reports

## Quick Start

### Prerequisites
- Python 3.8+
- MIDAS backend running
- Test dataset available

### Installation
cd midas/testing
pip install -r requirements.txt### Running Tests

#### Option 1: Automated Test Runner
python testing/run_tests.py#### Option 2: Direct Test Suite Execution
# Basic test run
python testing/midas_test_suite.py

# With custom backend URL
python testing/midas_test_suite.py --url http://localhost:8000

# Verbose logging
python testing/midas_test_suite.py --verbose#### Option 3: Custom Test Scenarios
from testing.midas_test_suite import MIDASTestSuite

# Run specific test scenario
test_suite = MIDASTestSuite()
test_suite.run_all_tests()

# Run individual tests
test_suite.test_data_ingestion()
test_suite.test_model_training()## Configuration

Edit `testing/test_config.py` to customize:

- Backend URL
- Test dataset path
- Test timeouts
- Algorithms to test
- Segmentation parameters

## Test Reports

After execution, the following reports are generated:

- **`midas_test_report.json`**: Detailed JSON report with all test results
- **`midas_test_report.html`**: Visual HTML report with charts and summaries
- **`midas_test_results.log`**: Execution log file

## Test Scenarios

### Basic Workflow
Tests core functionality:
1. Data ingestion → 2. Validation → 3. Model training → 4. Evaluation

### Advanced Workflow  
Includes segmentation and feature engineering:
1. Data processing → 2. Analysis → 3. Segmentation → 4. Feature engineering → 5. Advanced training

### Comprehensive Workflow
Tests ALL features in logical order (45+ individual tests)

## API Testing

The test suite validates:
- ✅ HTTP status codes
- ✅ Response structure
- ✅ Data integrity
- ✅ Error handling
- ✅ Performance (response times)

## Continuous Integration

### GitHub Actions Example
name: MIDAS Testing
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
    - name: Start backend
      run: |
        cd backend
        python run_server.py &
        sleep 10
    - name: Run tests
      run: |
        cd testing
        python run_tests.py## Troubleshooting

### Backend Connection Issues
# Check if backend is running
curl http://localhost:8000/docs

# Start backend manually
cd backend
python run_server.py### Test Dataset Issues
- Ensure `frontend/test-dataset.csv` exists
- Or set custom path: `python midas_test_suite.py --data path/to/dataset.csv`

### Common Errors
- **Connection refused**: Backend not running
- **File not found**: Test dataset missing
- **Timeout**: Increase timeout in config
- **Memory errors**: Reduce test data size

## Extending Tests

### Adding New Tests
1. Add method to `MIDASTestSuite` class
2. Follow naming convention: `test_feature_name`
3. Add to `TEST_SCENARIOS` in config
4. Update documentation

### Example New Test
def test_custom_feature(self):
    """Test custom feature"""
    payload = {"param": "value"}
    success, response = self._make_request('POST', '/custom-endpoint', json=payload)
    self._log_test_result("custom_feature", success, details=response)## Performance Testing

The suite includes basic performance validation:
- Response time monitoring
- Memory usage checks (for large datasets)
- Concurrent request handling

## Contributing

1. Follow existing code patterns
2. Add comprehensive error handling
3. Update documentation
4. Test locally before committing
5. Ensure backward compatibility

## License

Same as MIDAS project.
