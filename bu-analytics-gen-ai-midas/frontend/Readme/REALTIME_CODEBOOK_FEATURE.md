# Real-Time Dynamic Codebook Feature

## Overview
Enhanced the "View Codebook" feature to display **real-time, context-aware code** that reflects the user's actual configuration instead of generic placeholder code.

## What Changed

### Before (Static Codebook)
```python
# Load your dataset
df = pd.read_csv('your_dataset.csv')

# Define target variable
target_variable = 'target_column'

# Set number of folds
k_folds = 5
```

### After (Dynamic Codebook)
```python
# Load your dataset
df = pd.read_csv('loan_data_sample_1.csv')

# Define target variable
target_variable = 'loan_status'

# Selected variables for training: ['income', 'credit_score', 'employment_length', 'debt_to_income']
# Total: 4 variables

# Set number of folds
k_folds = 7

problem_type = 'classification'  # Detected from your data
```

## Features

### 1. Dynamic Context Injection
The codebook now receives and displays:
- ✅ **Actual dataset filename** (e.g., `loan_data_sample_1.csv`)
- ✅ **Real target variable** (e.g., `loan_status`)
- ✅ **Selected independent variables** with count
- ✅ **K-folds value** from user's setting
- ✅ **Problem type** (classification/regression)

### 2. Configuration Summary
At the top of the codebook, users now see their current configuration:

```
**Current Configuration:**
- Dataset: `loan_data_sample_1.csv`
- Target Variable: `loan_status`
- Selected Variables: 4 features
- K-Folds: 7
- Problem Type: Classification
```

### 3. Smart Code Replacement
The backend intelligently replaces placeholders:
- Dataset name: `'your_dataset.csv'` → `'loan_data_sample_1.csv'`
- Target variable: `'target_column'` → `'loan_status'`
- K-folds: `k_folds = 5` → `k_folds = 7`
- Problem type: Adds comment with detected type

## Implementation Details

### Backend Changes (`routes.py`)

#### New Query Parameters
```python
@chat_router.get("/model-codebook/{algorithm}")
async def get_model_codebook(
    algorithm: str,
    dataset_id: Optional[str] = None,
    target_variable: Optional[str] = None,
    selected_variables: Optional[str] = None,  # JSON string
    k_folds: Optional[int] = 5,
    problem_type: Optional[str] = None,
    current_user = Depends(get_current_user_dependency)
):
```

#### Context Resolution
1. Fetches dataset info from `dataset_manager` using `dataset_id`
2. Extracts actual dataset filename
3. Parses selected variables from JSON string
4. Applies replacements to all code sections
5. Augments description with current configuration

### Frontend Changes

#### Service Layer (`fastApiService.ts`)
```typescript
async getModelCodebook(
  algorithm: 'random_forest' | 'gradient_boosting' | 'logistic_regression',
  context?: {
    dataset_id?: string;
    target_variable?: string;
    selected_variables?: string[];
    k_folds?: number;
    problem_type?: 'classification' | 'regression';
  }
): Promise<ModelCodebookResponse>
```

#### Component Layer (`Step3_5SegmentationAgentAnalysis.tsx`)

**New Props:**
- `activeDatasetId`: Current dataset ID
- `targetVariable`: Current target variable

**Updated Handler:**
```typescript
const handleViewCodebook = async () => {
  const response = await fastApiService.getModelCodebook(
    selectedModel as 'random_forest' | 'gradient_boosting' | 'logistic_regression',
    {
      dataset_id: activeDatasetId,
      target_variable: targetVariable,
      selected_variables: selectedGlobalModelVariables.length > 0 
        ? selectedGlobalModelVariables 
        : undefined,
      k_folds: kFolds,
      problem_type: problemType
    }
  );
  // ...
};
```

#### Parent Component (`ModelBuilder.tsx`)
Passes new props to Step3_5:
```typescript
<Step3_5SegmentationAgentAnalysis
  // ... existing props ...
  activeDatasetId={activeDatasetId}
  targetVariable={datasetConfig?.target_variable || undefined}
/>
```

## User Experience

### Workflow
1. User uploads dataset (`loan_data_sample_1.csv`)
2. User sets target variable (`loan_status`)
3. User selects algorithm (Random Forest)
4. User configures k-folds (7)
5. User optionally selects specific variables
6. User clicks **"View Codebook"**
7. Modal displays code with **all their actual values**

### Benefits
- **Transparency**: Users see exactly what code runs for their data
- **Learning**: Users understand how their choices affect the code
- **Debugging**: Easier to spot configuration issues
- **Trust**: Clear visibility into backend implementation
- **Copy-Paste Ready**: Code can be copied and used elsewhere

## Technical Architecture

```
User Configuration (Frontend)
       ↓
FastAPI Service Layer
       ↓
Backend Endpoint (/model-codebook/{algorithm})
       ↓
Load Template from JSON
       ↓
Inject Real Context:
  - Get dataset name from dataset_manager
  - Replace all placeholders
  - Add configuration comments
       ↓
Return Customized Codebook
       ↓
Display in Modal with Context Summary
```

## Code Quality

### Type Safety
- ✅ Full TypeScript types throughout
- ✅ Optional parameters with proper defaults
- ✅ Proper null/undefined handling

### Error Handling
- ✅ Graceful fallbacks if dataset not found
- ✅ JSON parsing with try-catch
- ✅ Default values for missing parameters

### Performance
- ✅ Efficient string replacement
- ✅ Single pass through code sections
- ✅ No heavy computation
- ✅ Fast response time

## Files Modified

### Backend
1. `midas/backend/app/api/routes.py` (lines 2183-2299)
   - Added query parameters
   - Added context resolution logic
   - Added dynamic code replacement

### Frontend
1. `midas/frontend/src/services/fastApiService.ts` (lines 816-866)
   - Added context parameter to interface
   - Added query string building
   - Updated method signature

2. `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`
   - Added props: `activeDatasetId`, `targetVariable` (lines 25-26)
   - Updated component signature (lines 64-65)
   - Updated handler to pass context (lines 146-154)

3. `midas/frontend/src/pages/ModelBuilder.tsx` (lines 2954-2955)
   - Passed new props to Step3_5 component

## Testing Checklist

- [x] Codebook shows actual dataset name
- [x] Codebook shows actual target variable
- [x] Codebook shows selected variables count
- [x] Codebook shows user's k-folds value
- [x] Codebook shows detected problem type
- [x] Configuration summary appears at top
- [x] All algorithms (RF, GB, LR) work correctly
- [x] Graceful handling when dataset not loaded
- [x] No TypeScript errors
- [x] No runtime errors

## Future Enhancements

1. **Variable Details Section**: Show actual variable names and types
2. **Data Sample Preview**: Include first few rows of actual data
3. **Performance Metrics**: Show expected training time based on data size
4. **Export Options**: Download as actual executable .py or .ipynb file
5. **Comparison Mode**: Compare code for different algorithms side-by-side

## Summary

This enhancement transforms the codebook from a **static reference** to a **dynamic, personalized implementation guide** that reflects the user's exact configuration. Users can now see precisely what code will run with their data, making the system more transparent, educational, and trustworthy.

