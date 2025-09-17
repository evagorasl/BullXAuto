#!/usr/bin/env python3
"""
BullX Automation Startup Script

This script starts the BullX automation API server with automatic virtual environment management.
"""

import sys
import os
import subprocess
import logging
import venv
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
venv_path = current_dir / "venv"

def print_global_cleanup_command():
    """Print the command to remove global packages from requirements.txt"""
    print("\n" + "=" * 60)
    print("GLOBAL PACKAGE CLEANUP COMMAND")
    print("=" * 60)
    print("To remove packages from your global Python environment that are")
    print("listed in requirements.txt, run this command:")
    print()
    print("pip uninstall fastapi uvicorn selenium webdriver-manager sqlalchemy pydantic python-multipart asyncio-mqtt apscheduler requests python-dotenv -y")
    print()
    print("=" * 60)

def create_virtual_environment():
    """Create virtual environment if it doesn't exist"""
    if venv_path.exists():
        print("✓ Virtual environment already exists")
        return True
    
    print("Creating virtual environment...")
    try:
        venv.create(venv_path, with_pip=True)
        print("✓ Virtual environment created successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create virtual environment: {e}")
        return False

def get_venv_python():
    """Get the path to the Python executable in the virtual environment"""
    if os.name == 'nt':  # Windows
        return venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        return venv_path / "bin" / "python"

def get_venv_pip():
    """Get the path to the pip executable in the virtual environment"""
    if os.name == 'nt':  # Windows
        return venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        return venv_path / "bin" / "pip"

def check_dependencies():
    """Check if all required dependencies are installed in virtual environment"""
    venv_python = get_venv_python()
    
    try:
        # Test imports using the virtual environment Python
        test_script = '''
try:
    import fastapi
    import uvicorn
    import selenium
    import sqlalchemy
    import pydantic
    import apscheduler
    print("✓ All dependencies are installed")
    exit(0)
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    exit(1)
'''
        result = subprocess.run([str(venv_python), "-c", test_script], 
                              capture_output=True, text=True)
        print(result.stdout.strip())
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Error checking dependencies: {e}")
        return False

def install_dependencies():
    """Install dependencies from requirements.txt in virtual environment"""
    venv_pip = get_venv_pip()
    
    try:
        print("Installing dependencies in virtual environment...")
        subprocess.check_call([str(venv_pip), "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False

def start_application():
    """Start the application using the virtual environment"""
    venv_python = get_venv_python()
    
    try:
        print("Starting BullX Automation API...")
        print("API will be available at: http://localhost:8000")
        print("API documentation will be available at: http://localhost:8000/docs")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the server using virtual environment Python
        env = os.environ.copy()
        env['PYTHONPATH'] = str(current_dir)
        
        subprocess.run([
            str(venv_python), "-c",
            """
import sys
sys.path.insert(0, '.')
from main import app
import uvicorn
uvicorn.run(
    'main:app',
    host='0.0.0.0',
    port=8000,
    reload=True,
    log_level='info'
)
"""
        ], env=env)
        
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("BullX Automation API stopped")
        print("=" * 50)
    except Exception as e:
        print(f"✗ Error starting application: {e}")
        sys.exit(1)

def main():
    """Main startup function"""
    print("=" * 50)
    print("BullX Automation API Startup")
    print("=" * 50)
    
    # Show global cleanup command
    print_global_cleanup_command()
    
    # Create virtual environment
    if not create_virtual_environment():
        sys.exit(1)
    
    # Check if dependencies are installed in venv
    if not check_dependencies():
        response = input("Would you like to install dependencies now? (y/n): ")
        if response.lower() in ['y', 'yes']:
            if not install_dependencies():
                sys.exit(1)
        else:
            print("Please install dependencies manually and try again.")
            sys.exit(1)
    
    # Start the application
    start_application()

if __name__ == "__main__":
    main()
