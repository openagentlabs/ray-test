"""
Test script to check granular accuracy calculation and database storage.
This script will:
1. Check the database for existing granular accuracy data
2. Test the granular accuracy calculation function
3. Verify that segments are being created correctly
"""

import sqlite3
import json
import os
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def check_database_for_granular_accuracy(db_path: str = None):
    """Check the database for granular accuracy data"""
    print("=" * 80)
    print("CHECKING DATABASE FOR GRANULAR ACCURACY DATA")
    print("=" * 80)
    
    # Try to find the database path
    if db_path is None:
        # Check common locations
        possible_paths = [
            "data/message_states.db",
            "data/evaluation_results.db",
            "message_states.db",
            "evaluation_results.db"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                print(f"✅ Found database at: {db_path}")
                break
        
        if db_path is None:
            # Try to get from settings
            try:
                from app.core.config import settings
                db_path = settings.DATABASE_PATH
                print(f"📁 Using database path from settings: {db_path}")
            except:
                print("❌ Could not determine database path")
                return
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        print("   Trying to find database files in data/ directory...")
        data_dir = Path("data")
        if data_dir.exists():
            db_files = list(data_dir.glob("*.db"))
            if db_files:
                print(f"   Found {len(db_files)} database files:")
                for db_file in db_files:
                    print(f"      - {db_file}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all models
        cursor.execute("SELECT id, name, model_type, task_type FROM evaluation_models ORDER BY created_at DESC LIMIT 10")
        models = cursor.fetchall()
        
        print(f"\n📊 Found {len(models)} recent models:")
        for model_id, name, model_type, task_type in models:
            print(f"   - {model_id}: {name} ({model_type}, {task_type})")
            
            # Check for TEST granular accuracy
            cursor.execute("""
                SELECT COUNT(*) FROM granular_accuracy 
                WHERE model_id = ? AND split_type = 'test'
            """, (model_id,))
            test_count = cursor.fetchone()[0]
            
            # Check for TRAIN granular accuracy
            cursor.execute("""
                SELECT COUNT(*) FROM granular_accuracy 
                WHERE model_id = ? AND split_type = 'train'
            """, (model_id,))
            train_count = cursor.fetchone()[0]
            
            print(f"      TEST segments: {test_count}, TRAIN segments: {train_count}")
            
            # Get unique variables for TEST
            if test_count > 0:
                cursor.execute("""
                    SELECT DISTINCT variable FROM granular_accuracy 
                    WHERE model_id = ? AND split_type = 'test'
                """, (model_id,))
                test_vars = [row[0] for row in cursor.fetchall()]
                print(f"      TEST variables: {test_vars}")
                
                # Check for home_ownership specifically
                cursor.execute("""
                    SELECT COUNT(*) FROM granular_accuracy 
                    WHERE model_id = ? AND split_type = 'test' AND variable = 'home_ownership'
                """, (model_id,))
                ho_test_count = cursor.fetchone()[0]
                print(f"      TEST home_ownership segments: {ho_test_count}")
            
            # Get unique variables for TRAIN
            if train_count > 0:
                cursor.execute("""
                    SELECT DISTINCT variable FROM granular_accuracy 
                    WHERE model_id = ? AND split_type = 'train'
                """, (model_id,))
                train_vars = [row[0] for row in cursor.fetchall()]
                print(f"      TRAIN variables: {train_vars}")
                
                # Check for home_ownership specifically
                cursor.execute("""
                    SELECT COUNT(*) FROM granular_accuracy 
                    WHERE model_id = ? AND split_type = 'train' AND variable = 'home_ownership'
                """, (model_id,))
                ho_train_count = cursor.fetchone()[0]
                print(f"      TRAIN home_ownership segments: {ho_train_count}")
            
            print()
        
        conn.close()
        print("✅ Database check completed")
        
    except Exception as e:
        print(f"❌ Error checking database: {str(e)}")
        import traceback
        traceback.print_exc()


def check_training_results_json(models_dir: str = "models"):
    """Check training_results.json files for X_train_original_info"""
    print("\n" + "=" * 80)
    print("CHECKING TRAINING RESULTS JSON FILES")
    print("=" * 80)
    
    if not os.path.exists(models_dir):
        print(f"❌ Models directory not found: {models_dir}")
        return
    
    json_files = list(Path(models_dir).glob("*_training_results.json"))
    print(f"\n📁 Found {len(json_files)} training_results.json files")
    
    for json_file in json_files[:5]:  # Check first 5
        print(f"\n📄 {json_file.name}:")
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            model_id = data.get('model_id', 'unknown')
            print(f"   Model ID: {model_id}")
            
            # Check for X_train_original_info
            x_train_info = data.get('X_train_original_info')
            if x_train_info:
                print(f"   ✅ X_train_original_info found")
                if isinstance(x_train_info, dict):
                    print(f"      Keys: {list(x_train_info.keys())}")
                    if 'home_ownership' in x_train_info:
                        ho_info = x_train_info['home_ownership']
                        print(f"      home_ownership info: {ho_info}")
            else:
                print(f"   ⚠️ X_train_original_info NOT found")
            
            # Check for category_mappings
            cat_mappings = data.get('category_mappings', {})
            if cat_mappings:
                print(f"   ✅ category_mappings found for {len(cat_mappings)} features")
                if 'home_ownership' in cat_mappings:
                    ho_mapping = cat_mappings['home_ownership']
                    print(f"      home_ownership mapping: {ho_mapping}")
            else:
                print(f"   ⚠️ category_mappings NOT found")
            
            # Check for column_stats
            col_stats = data.get('column_stats', {})
            if col_stats:
                print(f"   ✅ column_stats found for {len(col_stats)} features")
                if 'home_ownership' in col_stats:
                    ho_stats = col_stats['home_ownership']
                    print(f"      home_ownership stats: {ho_stats}")
            else:
                print(f"   ⚠️ column_stats NOT found")
                
        except Exception as e:
            print(f"   ❌ Error reading {json_file.name}: {str(e)}")


def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("GRANULAR ACCURACY DIAGNOSTIC TOOL")
    print("=" * 80)
    
    # Check database
    check_database_for_granular_accuracy()
    
    # Check training results JSON files
    check_training_results_json()
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. If no granular accuracy data found in database, check logs for errors")
    print("2. If X_train_original_info missing, check training code")
    print("3. If segments exist but home_ownership missing, check feature matching logic")
    print("4. Run a new training to see detailed logs with enhanced logging")


if __name__ == "__main__":
    main()

