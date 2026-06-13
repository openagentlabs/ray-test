import re

file_path = r"c:\Users\saiyam268728\OneDrive - EXLService.com (I)\Pvt. Ltd\Desktop\UC-Github\LiteLLM\bu-analytics-gen-ai-midas\backend\app\services\model_training_auto_training.py"
# The path has spaces, let's fix it:
file_path = r"c:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Desktop\UC-Github\LiteLLM\bu-analytics-gen-ai-midas\backend\app\services\model_training_auto_training.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the train_single_algorithm function
match = re.search(r'(?s)(def train_single_algorithm\(algo_info\):.*?)(?=\n            # Create jobs for all algorithms)', content)
if not match:
    print('Could not find train_single_algorithm')
    exit(1)

body = match.group(1)

# Replace the docstring and algorithm_name assignment with our logic
header = """def train_single_algorithm(algo_info):
                \"\"\"Train a single algorithm - used for parallelization\"\"\"
                algorithm_name = algo_info['name']
                
                # --- CatBoost Raw Categorical Branch ---
                X_train_algo = X_train
                X_test_algo = X_test
                cat_features_list = []
                
                if algorithm_name == 'CatBoost' and hasattr(self, 'X_before_encoding') and self.X_before_encoding is not None:
                    _cand_cols = list(self.X_before_encoding.select_dtypes(include=['object', 'category', 'string']).columns)
                    cat_features_list = [c for c in _cand_cols if c in X_train_algo.columns]
                    
                    if cat_features_list:
                        try:
                            X_train_algo = X_train_algo.copy()
                            for c in cat_features_list:
                                X_train_algo[c] = self.X_before_encoding.loc[X_train_algo.index, c].astype(str)
                                
                            if X_test_algo is not None:
                                X_test_algo = X_test_algo.copy()
                                for c in cat_features_list:
                                    X_test_algo[c] = self.X_before_encoding.loc[X_test_algo.index, c].astype(str)
                            
                            self.logger.info(f"CatBoost: Injecting raw categoricals {cat_features_list}")
                        except Exception as e:
                            self.logger.warning(f"Failed to inject raw categoricals for CatBoost: {e}")
                            X_train_algo = X_train
                            X_test_algo = X_test
                            cat_features_list = []
                # ---------------------------------------"""

# We need to replace X_train and X_test inside the function body with X_train_algo and X_test_algo
# but NOT in the new header.
# So we split the body after the algorithm_name = algo_info['name']

split_pattern = r'def train_single_algorithm\(algo_info\):\s+"""Train a single algorithm - used for parallelization"""\s+algorithm_name = algo_info\[\'name\'\]'
parts = re.split(split_pattern, body)
if len(parts) != 2:
    print('Could not parse body')
    exit(1)

rest_of_body = parts[1]

# Replace X_train and X_test
rest_of_body = re.sub(r'\bX_train\b', 'X_train_algo', rest_of_body)
rest_of_body = re.sub(r'\bX_test\b', 'X_test_algo', rest_of_body)

# Add the cat_features logic before base params
rest_of_body = rest_of_body.replace(
    '                    # Create base model instance',
    "                    if algorithm_name == 'CatBoost' and cat_features_list:\n                        base_params['cat_features'] = cat_features_list\n\n                    # Create base model instance"
)

# Put the CatBoost logic at the top
new_body = header + rest_of_body

new_content = content[:match.start()] + new_body + content[match.end():]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Updated train_single_algorithm successfully')
