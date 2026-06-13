#!/usr/bin/env python3
"""
MIDAS System Readiness Check
Validates that all components are ready for testing
"""

import requests
import sys
import os
from pathlib import Path
import subprocess

def check_backend(url: str = "http://localhost:8000") -> bool:
    """Check if backend is accessible"""
    try:
        response = requests.get(f"{url}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ Backend is running and accessible")
            return True
        else:
            print(f"❌ Backend returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to backend: {e}")
        return False

def check_test_data(data_path: str) -> bool:
    """Check if test dataset exists and is valid"""
    try:
        path = Path(__file__).parent.parent / data_path
        if not path.exists():
            print(f"❌ Test dataset not found: {path}")
            return False
        
        import pandas as pd
        df = pd.read_csv(path)
        if len(df) == 0:
            print("❌ Test dataset is empty")
            return False
        
        print(f"✅ Test dataset found: {len(df)} rows, {len(df.columns)} columns")
        return True
        
    except Exception as e:
        print(f"❌ Error reading test dataset: {e}")
        return False

def check_dependencies() -> bool:
    """Check if required Python packages are installed"""
    required_packages = [
        'requests', 'pandas', 'numpy', 'matplotlib', 'seaborn'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r testing/requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_ports() -> bool:
    """Check if required ports are available"""
    import socket
    
    ports_to_check = [8000]  # Backend port
    
    for port in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is accessible")
        else:
            print(f"⚠️  Port {port} is not accessible (may be normal if backend not started)")
    
    return True  # Don't fail on port checks

def main():
    """Run system readiness checks"""
    print("🔍 MIDAS System Readiness Check")
    print("=" * 40)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Test Data", lambda: check_test_data("frontend/test-dataset.csv")),
        ("Backend Connection", lambda: check_backend("http://localhost:8000")),
        ("Network Ports", check_ports),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n🔍 Checking {check_name}...")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Error during {check_name} check: {e}")
            results.append(False)
    
    print("\n" + "=" * 40)
    print("📊 CHECK RESULTS SUMMARY")
    print("=" * 40)
    
    all_passed = all(results)
    
    for i, (check_name, _) in enumerate(checks):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"{check_name}: {status}")
    
    print(f"\nOverall Status: {'✅ READY' if all_passed else '❌ NOT READY'}")
    
    if not all_passed:
        print("\n🔧 To fix issues:")
        print("1. Install dependencies: pip install -r testing/requirements.txt")
        print("2. Ensure test dataset exists in frontend/test-dataset.csv")
        print("3. Start backend: cd backend && python run_server.py")
        print("4. Run tests: python testing/run_tests.py")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
