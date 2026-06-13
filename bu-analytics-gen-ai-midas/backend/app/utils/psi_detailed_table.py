"""
PSI Detailed Table Generator
Shows bin-by-bin breakdown: Expected Count, Expected %, Actual Count, Actual %, Difference
"""

import numpy as np
import pandas as pd
from app.utils.monotonicity import calculate_psi

def generate_psi_detailed_table(expected_scores, actual_scores, q=10):
    """
    Generate detailed PSI table showing bin-by-bin breakdown.
    
    Args:
        expected_scores: Training/reference scores
        actual_scores: Test/current scores
        q: Number of bins (default 10)
    
    Returns:
        DataFrame with detailed breakdown
    """
    expected_arr = np.asarray(expected_scores)
    actual_arr = np.asarray(actual_scores)
    
    print("=" * 100)
    print("PSI DETAILED BREAKDOWN TABLE")
    print("=" * 100)
    
    print(f"\nDataset Information:")
    print(f"  Expected (Training) samples: {len(expected_arr):,}")
    print(f"  Actual (Test) samples: {len(actual_arr):,}")
    print(f"  Number of bins: {q}")
    
    # Create bins based on expected distribution
    try:
        _, bin_edges = pd.qcut(expected_arr, q=q, retbins=True, duplicates="drop")
        
        if len(bin_edges) < 2:
            min_val = min(expected_arr.min(), actual_arr.min())
            max_val = max(expected_arr.max(), actual_arr.max())
            if min_val == max_val:
                print("\nError: No variation in scores")
                return None
            bin_edges = np.linspace(min_val, max_val, q + 1)
        else:
            min_val = min(expected_arr.min(), actual_arr.min())
            max_val = max(expected_arr.max(), actual_arr.max())
            bin_edges[0] = min_val - 1e-6
            bin_edges[-1] = max_val + 1e-6
    except Exception:
        min_val = min(expected_arr.min(), actual_arr.min())
        max_val = max(expected_arr.max(), actual_arr.max())
        if min_val == max_val:
            print("\nError: No variation in scores")
            return None
        bin_edges = np.linspace(min_val, max_val, q + 1)
    
    # Calculate counts
    expected_counts, _ = np.histogram(expected_arr, bins=bin_edges)
    actual_counts, _ = np.histogram(actual_arr, bins=bin_edges)
    
    # Calculate percentages
    expected_pct = expected_counts / len(expected_arr)
    actual_pct = actual_counts / len(actual_arr)
    
    # Avoid division by zero for PSI calculation
    expected_pct_for_psi = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct_for_psi = np.where(actual_pct == 0, 1e-6, actual_pct)
    
    # Calculate PSI contributions
    psi_contributions = (actual_pct_for_psi - expected_pct_for_psi) * np.log(actual_pct_for_psi / expected_pct_for_psi)
    
    # Calculate differences
    differences = actual_pct - expected_pct
    
    # Create table
    table_data = []
    for i in range(len(expected_counts)):
        table_data.append({
            'Bin': i + 1,
            'Bin_Range': f"[{bin_edges[i]:.4f}, {bin_edges[i+1]:.4f})",
            'Expected_Count': int(expected_counts[i]),
            'Expected_%': expected_pct[i],
            'Actual_Count': int(actual_counts[i]),
            'Actual_%': actual_pct[i],
            'Difference_%': differences[i],
            'PSI_Contribution': psi_contributions[i]
        })
    
    df = pd.DataFrame(table_data)
    
    # Print table
    print("\n" + "=" * 100)
    print("DETAILED PSI BREAKDOWN TABLE")
    print("=" * 100)
    print(f"\n{'Bin':<6} {'Bin Range':<25} {'Expected Count':<18} {'Expected %':<15} {'Actual Count':<18} {'Actual %':<15} {'Difference %':<15} {'PSI Contrib':<15}")
    print("-" * 100)
    
    for _, row in df.iterrows():
        print(f"{int(row['Bin']):<6} {row['Bin_Range']:<25} {int(row['Expected_Count']):<18} {row['Expected_%']:>14.4%}  {int(row['Actual_Count']):<18} {row['Actual_%']:>14.4%}  {row['Difference_%']:>14.4%}  {row['PSI_Contribution']:>14.6f}")
    
    total_psi = df['PSI_Contribution'].sum()
    total_expected_count = df['Expected_Count'].sum()
    total_actual_count = df['Actual_Count'].sum()
    
    print("-" * 100)
    print(f"{'TOTAL':<6} {'':<25} {int(total_expected_count):<18} {'100.00%':<15} {int(total_actual_count):<18} {'100.00%':<15} {'':<15} {total_psi:>14.6f}")
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Total PSI: {total_psi:.6f}")
    
    # Verify with code
    code_psi = calculate_psi(expected_arr, actual_arr, q=q)
    print(f"Code PSI: {code_psi:.6f}")
    print(f"Difference: {abs(total_psi - code_psi):.10f}")
    
    if abs(total_psi - code_psi) < 1e-6:
        print("[PASS] Calculations match!")
    else:
        print("[FAIL] Calculations don't match!")
    
    print(f"\nPSI Interpretation:")
    if total_psi < 0.1:
        print(f"  {total_psi:.4f} < 0.1 -> No significant population shift (Stable)")
    elif total_psi < 0.25:
        print(f"  0.1 <= {total_psi:.4f} < 0.25 -> Moderate population shift")
    else:
        print(f"  {total_psi:.4f} >= 0.25 -> Significant population shift")
    
    return df


def load_data_from_arrays(expected_scores, actual_scores, q=10):
    """
    Generate table from numpy arrays or lists.
    """
    return generate_psi_detailed_table(expected_scores, actual_scores, q=q)


def load_data_from_csv(expected_file=None, actual_file=None, score_column='score', q=10):
    """
    Load data from CSV files and generate table.
    
    Args:
        expected_file: Path to CSV with expected scores
        actual_file: Path to CSV with actual scores
        score_column: Name of column containing scores
        q: Number of bins
    """
    if expected_file and actual_file:
        expected_df = pd.read_csv(expected_file)
        actual_df = pd.read_csv(actual_file)
        
        expected_scores = expected_df[score_column].values
        actual_scores = actual_df[score_column].values
        
        return generate_psi_detailed_table(expected_scores, actual_scores, q=q)
    else:
        print("Please provide both expected_file and actual_file paths")
        return None


# Example usage
if __name__ == "__main__":
    print("PSI Detailed Table Generator")
    print("\nOption 1: Use example data")
    print("Option 2: Load from your data")
    print("\nFor now, showing example...")
    
    # Example with realistic data
    np.random.seed(42)
    expected_scores = np.random.beta(2, 2, size=5000)
    actual_scores = np.random.beta(3, 1.5, size=5000)
    
    df = generate_psi_detailed_table(expected_scores, actual_scores, q=10)
    
    print("\n" + "=" * 100)
    print("TO USE WITH YOUR DATA:")
    print("=" * 100)
    print("""
# Method 1: From arrays/lists
from app.utils.psi_detailed_table import load_data_from_arrays

expected_scores = [your_training_scores]  # List or numpy array
actual_scores = [your_test_scores]       # List or numpy array
df = load_data_from_arrays(expected_scores, actual_scores, q=10)

# Method 2: From CSV files
from app.utils.psi_detailed_table import load_data_from_csv

df = load_data_from_csv(
    expected_file='train_scores.csv',
    actual_file='test_scores.csv',
    score_column='score',
    q=10
)

# Method 3: Direct function call
from app.utils.psi_detailed_table import generate_psi_detailed_table

df = generate_psi_detailed_table(train_scores, test_scores, q=10)
    """)



