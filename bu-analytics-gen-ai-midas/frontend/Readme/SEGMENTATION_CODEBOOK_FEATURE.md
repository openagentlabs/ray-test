# Segmentation Codebook Feature

## Overview
Added a "View Codebook" feature for segmentation analysis, allowing users to see the backend implementation code for CART and CHAID segmentation methods.

## Changes Made

### 1. Created Segmentation Codebook Files

**Files Created:**
- `midas/backend/app/notebooks/cart_segmentation.json`
- `midas/backend/app/notebooks/chaid_segmentation.json`

Each codebook contains 10 sections covering:
1. Import Required Libraries
2. Load and Prepare Dataset
3. Data Preprocessing
4. Encode Categorical Variables
5. Initialize Model (CART with Gini or CHAID with Entropy)
6. Train Segmentation Model
7. Extract Segment Assignments
8. Extract Segment Rules (decision paths)
9. Segment Performance Metrics
10. Additional Analysis (Tree visualization for CART, Chi-squared for CHAID)

### 2. Backend Updates

**File:** `midas/backend/app/api/routes.py`

Added segmentation algorithms to the codebook endpoint:
```python
algorithm_files = {
    'random_forest': 'random_forest.json',
    'gradient_boosting': 'gradient_boosting.json',
    'logistic_regression': 'logistic_regression.json',
    'cart': 'cart_segmentation.json',      # NEW
    'chaid': 'chaid_segmentation.json'     # NEW
}
```

### 3. Frontend Service Updates

**File:** `midas/frontend/src/services/fastApiService.ts`

Updated TypeScript types to include segmentation methods:
```typescript
async getModelCodebook(
  algorithm: 'random_forest' | 'gradient_boosting' | 'logistic_regression' | 'cart' | 'chaid',
  // ... context parameters
): Promise<ModelCodebookResponse>
```

### 4. UI Component Updates

**File:** `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`

**Added:**
1. **New state:** `codebookType` to distinguish between model and segmentation codebooks
2. **New handler:** `handleViewSegmentationCodebook()` to fetch segmentation codebooks
3. **Two "View Codebook" buttons:**
   - One next to "Run Segmentation" button (Custom Segmentation)
   - One next to "Run Segmentation" button (Auto Segmentation)

**Button Placement:**
```tsx
// Custom Segmentation
<button onClick={onRunSegmentation}>Run Segmentation</button>
<button onClick={handleViewSegmentationCodebook}>View Codebook</button>

// Auto Segmentation  
<button onClick={onRunAutoSegmentation}>Run Segmentation</button>
<button onClick={handleViewSegmentationCodebook}>View Codebook</button>
```

## Features

### Dynamic Context
The segmentation codebooks show real-time configuration:
- **Dataset name**: Actual filename being used
- **Target variable**: User's selected target
- **Segmentation variables**: Selected variables for segmentation
- **Problem type**: Classification or regression
- **Method**: CART (Gini) or CHAID (Entropy)

### CART Codebook Highlights
- Uses `criterion='gini'` for classification
- Uses `criterion='squared_error'` for regression
- Shows tree visualization code
- Explains decision path extraction
- Demonstrates segment rule generation

### CHAID Codebook Highlights
- Uses `criterion='entropy'` for information gain
- Classification-only method
- Shows chi-squared statistical tests
- Demonstrates entropy calculations per segment
- Explains categorical variable handling

## User Experience

### Workflow
1. User selects segmentation mode (Custom or Auto)
2. User selects segmentation variables (if Custom mode)
3. User selects method (CART or CHAID)
4. User clicks **"View Codebook"** button
5. Modal opens showing the implementation code for selected method
6. Code includes user's actual:
   - Dataset filename
   - Target variable
   - Selected segmentation variables (if any)
   - Problem type

### Button States
- **Enabled**: Always enabled (no prerequisites)
- **Loading**: Shows spinner while fetching codebook
- **Disabled**: Only when already loading another codebook

## Visual Layout

```
┌─────────────────────────────────────────────────┐
│ Segmentation Analysis                           │
├─────────────────────────────────────────────────┤
│ Mode: [Custom] [Auto]                          │
│                                                 │
│ Variables: [...selected...]                    │
│ Parameters: Min Size, Max Segments             │
│ Method: ○ CART  ○ CHAID                       │
│                                                 │
│ [Run Segmentation] [View Codebook]             │
│      ↑ Both buttons side-by-side              │
└─────────────────────────────────────────────────┘
```

## Technical Details

### Context Passing
```typescript
const response = await fastApiService.getModelCodebook(
  segmentationMethod as 'cart' | 'chaid',
  {
    dataset_id: activeDatasetId,
    target_variable: targetVariable,
    selected_variables: segmentationMode === 'custom' && selectedSegmentationVariables.length > 0 
      ? selectedSegmentationVariables 
      : undefined,
    problem_type: problemType
  }
);
```

### Shared Modal
- Uses the same modal component as global model codebook
- Distinguishes between types using `codebookType` state
- Same expand/collapse, copy functionality
- Same styling and UX

## Code Sections Covered

### Both Methods Include:
1. **Data Loading**: Reading dataset and separating variables
2. **Preprocessing**: Handling missing values, encoding categoricals
3. **Model Initialization**: Setting up decision tree with appropriate criterion
4. **Training**: Fitting the segmentation model
5. **Segment Assignment**: Getting leaf node IDs for each record
6. **Rule Extraction**: Building human-readable decision paths
7. **Performance Metrics**: Size, proportion, event rates per segment

### CART-Specific:
- Gini impurity criterion
- Works for both classification and regression
- Tree visualization using matplotlib

### CHAID-Specific:
- Entropy criterion (information gain)
- Classification-only
- Chi-squared statistical tests
- Entropy calculations per segment

## Benefits

✅ **Transparency**: Users see exactly how segmentation works  
✅ **Educational**: Learn decision tree algorithms  
✅ **Debugging**: Understand segment creation logic  
✅ **Reproducibility**: Code can be copied and run independently  
✅ **Context-Aware**: Shows actual user configuration  
✅ **Comprehensive**: Covers entire segmentation pipeline  

## Files Modified/Created

### Created:
1. `midas/backend/app/notebooks/cart_segmentation.json`
2. `midas/backend/app/notebooks/chaid_segmentation.json`
3. `midas/SEGMENTATION_CODEBOOK_FEATURE.md` (this file)

### Modified:
1. `midas/backend/app/api/routes.py` (line 2206-2207)
   - Added CART and CHAID to algorithm files mapping

2. `midas/frontend/src/services/fastApiService.ts` (line 817)
   - Extended algorithm type union to include 'cart' | 'chaid'

3. `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`
   - Line 106: Added `codebookType` state
   - Lines 181-204: Added `handleViewSegmentationCodebook` handler
   - Lines 650-667: Added "View Codebook" button for Custom Segmentation
   - Lines 750-767: Added "View Codebook" button for Auto Segmentation

## Testing Checklist

- [x] CART codebook loads correctly
- [x] CHAID codebook loads correctly
- [x] Context is passed correctly (dataset, target, variables)
- [x] Buttons appear next to Run Segmentation buttons
- [x] Loading states work correctly
- [x] Modal displays codebook properly
- [x] Code sections are formatted correctly
- [x] No TypeScript errors
- [x] No runtime errors
- [x] Works for both Custom and Auto modes

## Consistency with Global Model Codebook

This feature maintains consistency with the global model codebook:
- ✅ Same modal component and styling
- ✅ Same button design and placement pattern
- ✅ Same loading states and error handling
- ✅ Same context-aware dynamic code generation
- ✅ Same user experience flow

