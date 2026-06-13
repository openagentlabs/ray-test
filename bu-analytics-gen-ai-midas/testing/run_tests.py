#!/usr/bin/env python3
"""
MIDAS Test Runner
Executes the comprehensive testing suite
"""

import subprocess
import sys
import os
from pathlib import Path

def check_backend_running(url: str = "http://localhost:8000") -> bool:
    """Check if MIDAS backend is running"""
    try:
        import requests
        response = requests.get(f"{url}/docs", timeout=10)
        return response.status_code == 200
    except:
        return False

def start_backend():
    """Start the MIDAS backend server"""
    print("🚀 Starting MIDAS Backend Server...")
    
    backend_dir = Path(__file__).parent.parent / "backend"
    os.chdir(backend_dir)
    
    # Try different ways to start the server
    try:
        # Method 1: Using run_server.py
        if (backend_dir / "run_server.py").exists():
            process = subprocess.Popen([sys.executable, "run_server.py"])
            print("✅ Backend started with run_server.py")
            return process
        
        # Method 2: Using main.py
        elif (backend_dir / "main.py").exists():
            process = subprocess.Popen([sys.executable, "main.py"])
            print("✅ Backend started with main.py")
            return process
        
        # Method 3: Using uvicorn directly
        else:
            process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", 
                "app.main:app", 
                "--host", "0.0.0.0", 
                "--port", "8000",
                "--reload"
            ])
            print("✅ Backend started with uvicorn")
            return process
            
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return None

def run_tests():
    """Run the comprehensive test suite"""
    print("🧪 Running MIDAS Comprehensive Test Suite...")
    print("📊 Using Lending Club dataset and data dictionary")
    
    # Check if backend is running
    if not check_backend_running():
        print("⚠️  Backend not running. Attempting to start it...")
        backend_process = start_backend()
        
        if backend_process:
            # Wait for backend to start
            import time
            print("⏳ Waiting for backend to initialize...")
            time.sleep(15)
            
            if not check_backend_running():
                print("❌ Backend failed to start properly")
                return False
        else:
            print("❌ Could not start backend")
            return False
    
    # Run the test suite
    try:
        result = subprocess.run([
            sys.executable, "testing/midas_test_suite.py",
            "--verbose",
            "--data", "testing/loan_data_sample 3.csv",
            "--dict", "testing/LCDataDictionary 2 4.csv"
        ], cwd=Path(__file__).parent.parent)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

def main():
    """Main function"""
    print("🎯 MIDAS Automated Testing System")
    print("=" * 40)
    print("📈 Testing with Lending Club Loan Data")
    print("📚 Including Data Dictionary Integration")
    
    success = run_tests()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed. Check the test report for details.")
        print("📄 Reports: midas_test_report.html and midas_test_report.json")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
