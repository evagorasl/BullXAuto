#!/usr/bin/env python3
"""
Test script to verify BullX Automation setup

This script performs basic tests to ensure the project is set up correctly.
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        # Test basic Python modules
        import json
        import logging
        import time
        print("✓ Basic Python modules imported successfully")
        
        # Test if we can import our modules (without dependencies)
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Test config import
        import config
        print("✓ Config module imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_file_structure():
    """Test if all required files exist"""
    print("\nTesting file structure...")
    
    required_files = [
        "main.py",
        "models.py", 
        "database.py",
        "chrome_driver.py",
        "background_tasks.py",
        "config.py",
        "auth.py",
        "middleware.py",
        "start.py",
        "requirements.txt",
        "README.md",
        "example_usage.py",
        "example_usage_with_auth.py",
        "routers/__init__.py",
        "routers/secure.py",
        "routers/public.py"
    ]
    
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - MISSING")
            missing_files.append(file)
    
    if missing_files:
        print(f"\nMissing files: {missing_files}")
        return False
    else:
        print("✓ All required files present")
        return True

def test_config():
    """Test configuration"""
    print("\nTesting configuration...")
    
    try:
        from config import config
        
        # Test basic config attributes
        assert hasattr(config, 'DATABASE_URL'), "DATABASE_URL not found in config"
        assert hasattr(config, 'CHROME_PROFILES'), "CHROME_PROFILES not found in config"
        assert hasattr(config, 'BULLX_BASE_URL'), "BULLX_BASE_URL not found in config"
        
        print("✓ Configuration structure is valid")
        print(f"  Database URL: {config.DATABASE_URL}")
        print(f"  BullX URL: {config.BULLX_BASE_URL}")
        print(f"  Chrome Profiles: {list(config.CHROME_PROFILES.keys())}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_chrome_profiles():
    """Test Chrome profile paths"""
    print("\nTesting Chrome profile paths...")
    
    try:
        from config import config
        
        for profile_name, profile_path in config.CHROME_PROFILES.items():
            # Check if the parent directory exists (the profile itself might not exist yet)
            parent_dir = Path(profile_path).parent
            
            if parent_dir.exists():
                print(f"✓ {profile_name}: Parent directory exists")
            else:
                print(f"⚠ {profile_name}: Parent directory does not exist - {parent_dir}")
                print(f"  You may need to create Chrome profiles manually")
        
        return True
        
    except Exception as e:
        print(f"✗ Chrome profile test failed: {e}")
        return False

def test_dependencies_availability():
    """Test if dependencies can be imported (if installed)"""
    print("\nTesting dependency availability...")
    
    dependencies = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("selenium", "Selenium"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("apscheduler", "APScheduler"),
        ("webdriver_manager", "WebDriver Manager")
    ]
    
    available = []
    missing = []
    
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
            available.append(display_name)
        except ImportError:
            print(f"✗ {display_name} - Not installed")
            missing.append(display_name)
    
    if missing:
        print(f"\nMissing dependencies: {missing}")
        print("Install with: pip install -r requirements.txt")
        return False
    else:
        print("✓ All dependencies are available")
        return True

def main():
    """Main test function"""
    print("=" * 60)
    print("BullX Automation - Setup Test")
    print("=" * 60)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Basic Imports", test_imports),
        ("Configuration", test_config),
        ("Chrome Profiles", test_chrome_profiles),
        ("Dependencies", test_dependencies_availability)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'-' * 40}")
        print(f"Running: {test_name}")
        print(f"{'-' * 40}")
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Your BullX Automation setup looks good.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Set up Chrome profiles (Saruman and Gandalf)")
        print("3. Start the API: python start.py")
        print("4. Test with: python example_usage.py")
    else:
        print(f"\n⚠ {failed} test(s) failed. Please address the issues above.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
