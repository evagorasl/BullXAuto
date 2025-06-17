#!/usr/bin/env python3
"""
BullX Automation Startup Script

This script starts the BullX automation API server.
"""

import sys
import os
import subprocess
import logging
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import selenium
        import sqlalchemy
        import pydantic
        import apscheduler
        print("✓ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False

def install_dependencies():
    """Install dependencies from requirements.txt"""
    try:
        print("Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False

def main():
    """Main startup function"""
    print("=" * 50)
    print("BullX Automation API Startup")
    print("=" * 50)
    
    # Check if dependencies are installed
    if not check_dependencies():
        response = input("Would you like to install dependencies now? (y/n): ")
        if response.lower() in ['y', 'yes']:
            if not install_dependencies():
                sys.exit(1)
        else:
            print("Please install dependencies manually and try again.")
            sys.exit(1)
    
    # Import and start the application
    try:
        print("Starting BullX Automation API...")
        print("API will be available at: http://localhost:8000")
        print("API documentation will be available at: http://localhost:8000/docs")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Import main after dependencies are confirmed
        from main import app
        import uvicorn
        
        # Start the server
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("BullX Automation API stopped")
        print("=" * 50)
    except Exception as e:
        print(f"✗ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
