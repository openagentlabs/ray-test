# View Codebook Feature - Visual Guide

## User Interface Changes

### Before (Original UI)
```
┌─────────────────────────────────────────────────────┐
│ Global Supervised Model Training                    │
├─────────────────────────────────────────────────────┤
│ Problem Type: Classification                        │
│                                                      │
│ 1. Select Algorithm for Global Model                │
│   ○ Random Forest                                   │
│   ○ Gradient Boosting                               │
│   ○ Logistic Regression                             │
│                                                      │
│ 2. K-Fold Cross Validation                          │
│   Number of Folds: [5 ▼]                           │
│                                                      │
│ 3. Train Global Model                               │
│   [Train Global Model]                              │
└─────────────────────────────────────────────────────┘
```

### After (With View Codebook Button)
```
┌─────────────────────────────────────────────────────┐
│ Global Supervised Model Training  [📖 View Codebook]│ ← NEW BUTTON
├─────────────────────────────────────────────────────┤
│ Problem Type: Classification                        │
│                                                      │
│ 1. Select Algorithm for Global Model                │
│   ● Random Forest  ← Selected                      │
│   ○ Gradient Boosting                               │
│   ○ Logistic Regression                             │
│                                                      │
│ 2. K-Fold Cross Validation                          │
│   Number of Folds: [5 ▼]                           │
│                                                      │
│ 3. Train Global Model                               │
│   [Train Global Model]                              │
└─────────────────────────────────────────────────────┘
```

## Modal View (When Codebook is Opened)

```
┌──────────────────────────────────────────────────────────────────┐
│ [Overlay - Semi-transparent Black Background]                    │
│                                                                   │
│   ┌────────────────────────────────────────────────────────┐    │
│   │ 📖 Random Forest Global Model Training            [✕]  │    │
│   │ [Gradient Header: Indigo → Purple]                     │    │
│   ├────────────────────────────────────────────────────────┤    │
│   │ This codebook demonstrates the backend code used to    │    │
│   │ train a Random Forest model with k-fold...             │    │
│   │                                                         │    │
│   │ ┌──────────────────────────────────────────────────┐  │    │
│   │ │ ① 1. Import Required Libraries                   │  │    │
│   │ ├──────────────────────────────────────────────────┤  │    │
│   │ │ ┌──────────────────────────────────────────────┐ │  │    │
│   │ │ │ import pandas as pd                          │ │  │    │
│   │ │ │ import numpy as np                           │ │  │    │
│   │ │ │ from sklearn.ensemble import ...             │ │  │    │
│   │ │ └──────────────────────────────────────────────┘ │  │    │
│   │ └──────────────────────────────────────────────────┘  │    │
│   │                                                         │    │
│   │ ┌──────────────────────────────────────────────────┐  │    │
│   │ │ ② 2. Load and Prepare Dataset                    │  │    │
│   │ ├──────────────────────────────────────────────────┤  │    │
│   │ │ ┌──────────────────────────────────────────────┐ │  │    │
│   │ │ │ df = pd.read_csv('your_dataset.csv')        │ │  │    │
│   │ │ │ target_variable = 'target_column'           │ │  │    │
│   │ │ └──────────────────────────────────────────────┘ │  │    │
│   │ └──────────────────────────────────────────────────┘  │    │
│   │                                                         │    │
│   │ ... (8 more sections)                                  │    │
│   │                                                         │    │
│   │ [Scrollable Content Area]                              │    │
│   │                                                         │    │
│   ├────────────────────────────────────────────────────────┤    │
│   │                                         [Close]         │    │
│   └────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Button States

### Enabled (Model Selected)
```
┌─────────────────────────┐
│ 📖 View Codebook        │  ← Indigo background, white text
│ (Hover: darker indigo)  │
└─────────────────────────┘
```

### Disabled (No Model Selected)
```
┌─────────────────────────┐
│ 📖 View Codebook        │  ← Gray background, cursor not-allowed
└─────────────────────────┘
```

### Loading State
```
┌─────────────────────────┐
│ ⟳ Loading...            │  ← Spinner animation
└─────────────────────────┘
```

## Code Section Styling

Each code section appears as:
```
┌────────────────────────────────────────────┐
│ ① Section Title                            │  ← Numbered badge
├────────────────────────────────────────────┤
│ ┌────────────────────────────────────────┐ │
│ │ # Dark background (Gray-900)           │ │
│ │ # Light text (Gray-100)                │ │
│ │ # Monospace font                       │ │
│ │                                        │ │
│ │ def example_code():                    │ │
│ │     return "formatted nicely"          │ │
│ └────────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

## Color Scheme

### Button & Modal Header
- **Primary**: Indigo-600 (#4F46E5)
- **Hover**: Indigo-700 (#4338CA)
- **Gradient**: Indigo-500 → Purple-600

### Code Blocks
- **Background**: Gray-900 (#111827)
- **Text**: Gray-100 (#F3F4F6)
- **Font**: Monospace (system default)

### Modal
- **Background**: White (#FFFFFF)
- **Border**: Gray-200 (#E5E7EB)
- **Overlay**: Black with 50% opacity

## Responsive Design

- **Modal Width**: Maximum 4xl (896px)
- **Modal Height**: Maximum 90vh (90% of viewport height)
- **Content**: Fully scrollable
- **Mobile-friendly**: Adapts to smaller screens

## Accessibility

- ✅ Keyboard accessible (Tab navigation)
- ✅ Close button in header and footer
- ✅ Click outside modal to close
- ✅ Clear visual feedback for states
- ✅ High contrast code blocks
- ✅ Descriptive button text
- ✅ Loading state indicators

## Integration Points

### Data Flow
```
User Clicks Button
       ↓
fastApiService.getModelCodebook(algorithm)
       ↓
GET /chat/model-codebook/{algorithm}
       ↓
Backend reads JSON file
       ↓
Returns ModelCodebookResponse
       ↓
Modal displays sections
```

### Error Handling
```
Failed to Load
       ↓
Alert: "Failed to load codebook. Please try again."
       ↓
Modal stays closed
       ↓
User can retry
```

## Summary

This implementation provides a clean, professional way to view the backend code for each ML algorithm without disrupting the existing UI. The codebook opens in a well-designed modal with syntax-friendly code presentation, making it easy for users to understand how their models are being trained.

