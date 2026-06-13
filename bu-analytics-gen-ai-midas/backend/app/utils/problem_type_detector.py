import pandas as pd
import numpy as np
from typing import Union
from app.models.schemas import ProblemType


def infer_problem_type(y: pd.Series) -> ProblemType:
    """
    Infer problem type (classification or regression) based on target variable characteristics
    
    Args:
        y: Target variable series
        
    Returns:
        ProblemType: CLASSIFICATION or REGRESSION
    """
    # Check if target is non-numeric or boolean
    if not pd.api.types.is_numeric_dtype(y):
        return ProblemType.CLASSIFICATION
    
    # Check if target is boolean
    if y.dtype == bool:
        return ProblemType.CLASSIFICATION
    
    # For numeric targets, check unique values
    unique_count = y.nunique()
    total_count = len(y)
    unique_ratio = unique_count / total_count
    
    # Enhanced logic for better continuous variable detection
    # Check if the variable represents continuous measurements (like rates, amounts, etc.)
    if unique_count > 50:  # More than 50 unique values, likely continuous
        return ProblemType.REGRESSION
    
    # Check if unique values are integers and represent counts/categories
    if unique_count <= 20 and unique_ratio <= 0.05:
        # Additional check: if values are mostly integers and small, likely classification
        if all(isinstance(val, (int, np.integer)) or (isinstance(val, float) and val.is_integer()) 
               for val in y.dropna().unique()[:10]):  # Check first 10 unique values
            return ProblemType.CLASSIFICATION
    
    # Special case: binary variables (0/1) should always be classification
    if unique_count == 2:
        unique_vals = sorted(y.dropna().unique())
        if unique_vals == [0, 1] or unique_vals == [0.0, 1.0]:
            return ProblemType.CLASSIFICATION
    
    # For variables with moderate unique values, check if they represent continuous measurements
    # by looking at the range and distribution
    if unique_count > 20:
        return ProblemType.REGRESSION
    
    # Default to regression for numeric variables unless clearly categorical
    return ProblemType.REGRESSION
