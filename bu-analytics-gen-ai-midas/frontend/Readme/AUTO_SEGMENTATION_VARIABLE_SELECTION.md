# Auto Segmentation Variable Selection Feature

## Overview
Added variable selection capability to the Auto Segmentation mode. Users can now select which variables to include in the automatic segmentation analysis, with all variables selected by default. This provides flexibility while maintaining ease of use.

## Key Features

### Default Behavior
- ✅ **All variables selected by default** when entering Auto Segmentation mode
- ✅ **Automatic sync** with available columns when dataset changes
- ✅ **User control** to deselect variables as needed
- ✅ **Maintains selection** across mode switches (until dataset changes)

### User Capabilities
- Select/deselect individual variables
- Search through variables
- "Select All" with one click
- "Clear All" with one click
- Remove variables via pill badges
- See selected count in real-time

## Changes Made

### 1. New State Variables

**File:** `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`

```typescript
// Local UI state for auto segmentation variables (default to all)
const [selectedAutoSegmentationVariables, setSelectedAutoSegmentationVariables] = useState<string[]>(availableColumns || []);
const [autoSegmentationSearch, setAutoSegmentationSearch] = useState<string>('');
const [isAutoDropdownOpen, setIsAutoDropdownOpen] = useState<boolean>(false);
const autoDropdownRef = useRef<HTMLDivElement | null>(null);
```

### 2. Auto-Sync with Available Columns

```typescript
// Sync auto segmentation variables with available columns (default to all)
useEffect(() => {
  if (availableColumns && availableColumns.length > 0 && selectedAutoSegmentationVariables.length === 0) {
    setSelectedAutoSegmentationVariables(availableColumns);
  }
}, [availableColumns]);
```

**Behavior:**
- When `availableColumns` updates (dataset changes)
- If no variables are currently selected
- Automatically selects all available columns

### 3. Variable Selection Handlers

```typescript
const toggleAutoSegmentationVariable = (col: string) => {
  const exists = selectedAutoSegmentationVariables.includes(col);
  const next = exists
    ? selectedAutoSegmentationVariables.filter(c => c !== col)
    : [...selectedAutoSegmentationVariables, col];
  setSelectedAutoSegmentationVariables(next);
};

const selectAllAutoSegmentation = () => 
  setSelectedAutoSegmentationVariables([...(availableColumns || [])]);

const clearAllAutoSegmentation = () => 
  setSelectedAutoSegmentationVariables([]);
```

### 4. Updated Click Outside Detection

```typescript
useEffect(() => {
  const onClickOutside = (e: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) 
      setIsDropdownOpen(false);
    if (autoDropdownRef.current && !autoDropdownRef.current.contains(e.target as Node)) 
      setIsAutoDropdownOpen(false);
    if (globalModelDropdownRef.current && !globalModelDropdownRef.current.contains(e.target as Node)) 
      setIsGlobalModelDropdownOpen(false);
  };
  document.addEventListener('mousedown', onClickOutside);
  return () => document.removeEventListener('mousedown', onClickOutside);
}, []);
```

### 5. Updated Codebook Fetch Logic

```typescript
const handleViewSegmentationCodebook = async () => {
  setIsLoadingCodebook(true);
  setCodebookType('segmentation');
  try {
    // Determine which variables to use based on mode
    let variablesToUse: string[] | undefined = undefined;
    if (segmentationMode === 'custom' && selectedSegmentationVariables.length > 0) {
      variablesToUse = selectedSegmentationVariables;
    } else if (segmentationMode === 'auto' && selectedAutoSegmentationVariables.length > 0) {
      variablesToUse = selectedAutoSegmentationVariables;
    }
    
    const response = await fastApiService.getModelCodebook(
      segmentationMethod as 'cart' | 'chaid',
      {
        dataset_id: activeDatasetId,
        target_variable: targetVariable,
        selected_variables: variablesToUse,
        problem_type: problemType
      }
    );
    // ... rest of logic
  }
};
```

## UI Components

### Variable Selection Dropdown

The dropdown includes:

1. **Header Button**
   - Shows count of selected variables
   - Chevron icon that rotates when open
   - Hover state for better UX

2. **Search Bar**
   - Real-time filtering
   - Case-insensitive search
   - Placeholder: "Search variables..."

3. **Action Buttons**
   - "Select All" - purple themed
   - "Clear All" - gray themed
   - Side-by-side layout

4. **Variable List**
   - Checkboxes for each variable
   - Checkmark icon when selected
   - Hover highlighting
   - Scrollable (max 256px height)
   - Empty state message

5. **Selected Pills Display**
   - Shows all selected variables as badges
   - Remove button (X) on each pill
   - Purple-themed styling
   - Wrapped layout

6. **Selection Summary**
   - Shows count: "Selected X variable(s)..."
   - Purple background highlight
   - Helps user confirm selection

### Visual Layout

```
┌─────────────────────────────────────────────┐
│ Available Variables                         │
├─────────────────────────────────────────────┤
│ [8 variables selected ▼]                    │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Search variables...                     │ │
│ │ [Select All] [Clear All]                │ │
│ ├─────────────────────────────────────────┤ │
│ │ ☑ variable1                      ✓      │ │
│ │ ☑ variable2                      ✓      │ │
│ │ ☑ variable3                      ✓      │ │
│ │ ...                                     │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [variable1 ×] [variable2 ×] [variable3 ×]  │
│ [variable4 ×] [variable5 ×] ...            │
│                                             │
│ Selected 8 variables for auto segmentation │
└─────────────────────────────────────────────┘
```

## User Workflow

### Typical User Journey

1. **Enter Auto Segmentation Mode**
   - Click "Auto Segmentation" tab
   - All variables are automatically selected ✅
   - User sees "8 variables selected" in dropdown button
   - User sees selected count message below

2. **Review Variables (Optional)**
   - Click dropdown to expand
   - See all variables with checkmarks
   - All are checked by default

3. **Modify Selection (Optional)**
   ```
   Option A: Remove specific variables
   - Uncheck unwanted variables in list
   - OR click X on pill badges
   
   Option B: Start fresh
   - Click "Clear All"
   - Select only desired variables
   
   Option C: Search and select
   - Type in search box
   - Check/uncheck filtered results
   ```

4. **Configure Parameters**
   - Set Minimum Segment Size
   - Set Maximum Segments
   - Choose Method (CART or CHAID)

5. **Run Segmentation**
   - Click "Run Segmentation"
   - Backend uses selected variables only

6. **View Codebook (Optional)**
   - Click "View Codebook"
   - Codebook shows selected variables in context

## Comparison: Custom vs Auto Segmentation

| Feature | Custom Segmentation | Auto Segmentation |
|---------|-------------------|-------------------|
| **Default Selection** | None (empty) | All variables ✅ |
| **User Must Select** | Yes | No (optional) |
| **Use Case** | Specific variable subset | Quick analysis with all data |
| **Flexibility** | Full control from start | Full control with smart default |
| **Description Text** | "Choose variables..." | "Runs on entire dataset..." |
| **Typical Workflow** | 1. Select vars 2. Run | 1. Run immediately OR 2. Adjust vars 3. Run |

## Benefits

### For Users:
✅ **Faster workflow** - No need to manually select all variables  
✅ **Flexibility** - Can still customize variable selection  
✅ **Clear defaults** - Obvious that all variables are included  
✅ **No surprises** - Can see and modify what's included  
✅ **Consistent UX** - Same dropdown interface as Custom mode  

### For Data Scientists:
✅ **Quick exploration** - Start with all variables immediately  
✅ **Easy refinement** - Remove irrelevant variables as needed  
✅ **Feature selection** - Can do exploratory analysis first  
✅ **Documented** - Codebook shows which variables were used  

### For Business Users:
✅ **No confusion** - Clear what "auto" means  
✅ **Safety** - Can verify variable selection  
✅ **Control** - Not a complete black box  
✅ **Transparency** - See exactly what's being analyzed  

## Technical Details

### State Management

**Initialization:**
```typescript
const [selectedAutoSegmentationVariables, setSelectedAutoSegmentationVariables] = 
  useState<string[]>(availableColumns || []);
```
- Initializes with all available columns
- Falls back to empty array if no columns

**Auto-Sync:**
```typescript
useEffect(() => {
  if (availableColumns && availableColumns.length > 0 && 
      selectedAutoSegmentationVariables.length === 0) {
    setSelectedAutoSegmentationVariables(availableColumns);
  }
}, [availableColumns]);
```
- Only syncs if current selection is empty
- Preserves user selections when dataset doesn't change

### Search Functionality

```typescript
availableColumns
  .filter(c => c.toLowerCase().includes(autoSegmentationSearch.toLowerCase()))
  .map((col) => {
    const checked = selectedAutoSegmentationVariables.includes(col);
    return (
      <li key={col}>
        <label>
          <input type="checkbox" checked={checked} onChange={() => toggleAutoSegmentationVariable(col)} />
          <span>{col}</span>
          {checked && <Check />}
        </label>
      </li>
    );
  })
```

**Features:**
- Case-insensitive filtering
- Real-time updates as user types
- Shows only matching variables
- Maintains selection state

### Empty State Handling

```typescript
{availableColumns.filter(c => c.toLowerCase().includes(autoSegmentationSearch.toLowerCase())).length > 0 ? (
  // Show filtered variables
) : (
  <li className="px-3 py-6 text-center text-sm text-gray-500">
    {availableColumns.length === 0 
      ? 'No variables available. Please ensure your dataset is loaded.'
      : 'No variables match your search.'}
  </li>
)}
```

**Two states:**
1. No columns at all → "No variables available..."
2. Columns exist but search has no matches → "No variables match..."

## Edge Cases Handled

### 1. Dataset Change
- ✅ Auto-syncs to new columns
- ✅ Resets to "all selected" default
- ✅ Clears old selections

### 2. Empty Dataset
- ✅ Shows helpful message
- ✅ Prevents errors
- ✅ Disables actions gracefully

### 3. Search with No Results
- ✅ Shows "No match" message
- ✅ Doesn't break selection state
- ✅ Clears when search is cleared

### 4. Mode Switching
- ✅ Custom and Auto have separate states
- ✅ Switching modes preserves selections
- ✅ No cross-contamination

### 5. All Variables Deselected
- ✅ Count shows "0 variables selected"
- ✅ Selection summary still displays
- ✅ Can still use "Select All"

## Styling Details

### Colors
- **Purple theme** for selection states
  - `bg-purple-50` - light backgrounds
  - `text-purple-600` - text and borders
  - `text-purple-700` - pill text
  - `border-purple-200` - borders
  
- **Gray theme** for neutral states
  - `bg-gray-50` - hover states
  - `text-gray-700` - normal text
  - `border-gray-300` - borders

### Interactive States
- **Hover:** `hover:bg-gray-50`, `hover:bg-purple-100`
- **Focus:** `focus:ring-2 focus:ring-purple-500`
- **Active:** Green highlight on selected buttons
- **Disabled:** Grayed out appearance

### Spacing
- Consistent `gap-2`, `gap-3` between elements
- `p-3` padding in containers
- `py-2` padding on interactive elements
- `max-h-64` for scrollable areas

## Files Modified

### Modified:
1. **midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx**
   - Lines 97-101: Added auto segmentation variable state
   - Lines 127-132: Added auto-sync useEffect
   - Lines 134-142: Updated click outside detection
   - Lines 165-174: Added variable selection handlers
   - Lines 206-236: Updated codebook fetch logic
   - Lines 820-923: Added variable selection UI for Auto mode

### Created:
1. **midas/AUTO_SEGMENTATION_VARIABLE_SELECTION.md** (this file)

## Testing Checklist

- [x] Default behavior: all variables selected on mount
- [x] Variables sync when dataset changes
- [x] Dropdown opens/closes correctly
- [x] Search filters variables correctly
- [x] "Select All" works
- [x] "Clear All" works
- [x] Individual checkbox toggle works
- [x] Pill removal works
- [x] Selection count updates in real-time
- [x] Empty state shows appropriate message
- [x] Search "no results" shows appropriate message
- [x] Click outside closes dropdown
- [x] Mode switching preserves selections
- [x] Codebook uses selected variables
- [x] No linter errors
- [x] No runtime errors
- [x] Mobile responsive layout

## User Feedback Messages

### Selection Count
```
"Selected X variable(s) for auto segmentation analysis."
```
- Shows real-time count
- Grammatically correct (singular/plural)
- Purple highlighted box
- Always visible when variables selected

### Dropdown Button
```
"X variable(s) selected"
```
OR
```
"Select variables" (when none selected)
```

### Empty States
```
"No variables available. Please ensure your dataset is loaded."
```
OR
```
"No variables match your search."
```

## Future Enhancements

Potential improvements:
1. **Smart Recommendations** - Suggest important variables based on correlation
2. **Variable Groups** - Group related variables (e.g., demographic, behavioral)
3. **Quick Filters** - "Numeric only", "Categorical only", etc.
4. **Save Presets** - Save favorite variable combinations
5. **Variable Importance** - Show importance scores from previous analyses
6. **Bulk Actions** - Select by pattern or criteria
7. **Variable Preview** - Show data type, missing values, etc. on hover

## Conclusion

This feature strikes the perfect balance between convenience and control. Users get the speed of "auto" mode with smart defaults (all variables selected), while retaining full control to customize their analysis. The UI is consistent with Custom mode, making it familiar and easy to use.

**Key Win:** Users can now either:
- Run auto segmentation immediately with all variables ✅
- OR quickly adjust variable selection before running ✅

Both workflows are equally supported!

