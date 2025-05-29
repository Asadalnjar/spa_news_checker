#!/usr/bin/env python3
"""
Setup script for SPA News Monitor
Helps with initial configuration and dependency installation.
"""

import os
import sys
import json
import subprocess
from pathlib import Path


def install_dependencies():
    """Install required Python packages."""
    print("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing dependencies: {e}")
        return False


def setup_config():
    """Interactive configuration setup."""
    print("\n=== SPA News Monitor Configuration Setup ===")
    
    config_file = "config.json"
    
    # Load existing config or create new one
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        print("Found existing configuration. You can update the values below.")
    else:
        config = {
            "target_url": "https://www.bbc.com/arabic",
            "database_path": "news_monitor.db",
            "openai_api_key": "",
            "openai_model": "gpt-3.5-turbo",
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "to_email": ""
            }
        }
    
    print("\n1. OpenAI Configuration:")
    api_key = input(f"Enter your OpenAI API key [{config.get('openai_api_key', '')}]: ").strip()
    if api_key:
        config['openai_api_key'] = api_key
    
    model = input(f"Enter OpenAI model [{config.get('openai_model', 'gpt-3.5-turbo')}]: ").strip()
    if model:
        config['openai_model'] = model
    
    print("\n2. Email Configuration:")
    print("Note: For Gmail, use an App Password instead of your regular password.")
    print("Enable 2FA and generate an App Password at: https://myaccount.google.com/apppasswords")
    
    smtp_server = input(f"SMTP Server [{config['email'].get('smtp_server', 'smtp.gmail.com')}]: ").strip()
    if smtp_server:
        config['email']['smtp_server'] = smtp_server
    
    smtp_port = input(f"SMTP Port [{config['email'].get('smtp_port', 587)}]: ").strip()
    if smtp_port:
        config['email']['smtp_port'] = int(smtp_port)
    
    username = input(f"Email Username [{config['email'].get('username', '')}]: ").strip()
    if username:
        config['email']['username'] = username
        if not config['email'].get('from_email'):
            config['email']['from_email'] = username
    
    password = input(f"Email Password/App Password [{config['email'].get('password', '')}]: ").strip()
    if password:
        config['email']['password'] = password
    
    from_email = input(f"From Email [{config['email'].get('from_email', '')}]: ").strip()
    if from_email:
        config['email']['from_email'] = from_email
    
    to_email = input(f"To Email (recipient) [{config['email'].get('to_email', '')}]: ").strip()
    if to_email:
        config['email']['to_email'] = to_email
    
    print("\n3. Target URL Configuration:")
    target_url = input(f"Target URL [{config.get('target_url', '')}]: ").strip()
    if target_url:
        config['target_url'] = target_url
    
    # Save configuration
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Configuration saved to {config_file}")
        return True
    except Exception as e:
        print(f"✗ Error saving configuration: {e}")
        return False


def validate_config():
    """Validate the configuration file."""
    print("\n=== Validating Configuration ===")
    
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        errors = []
        
        # Check required fields
        if not config.get('openai_api_key') or config['openai_api_key'] == 'YOUR_OPENAI_API_KEY_HERE':
            errors.append("OpenAI API key is missing or not set")
        
        if not config.get('email', {}).get('username'):
            errors.append("Email username is missing")
        
        if not config.get('email', {}).get('password'):
            errors.append("Email password is missing")
        
        if not config.get('email', {}).get('to_email'):
            errors.append("Recipient email is missing")
        
        if errors:
            print("✗ Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("✓ Configuration validation passed")
            return True
            
    except FileNotFoundError:
        print("✗ Configuration file not found")
        return False
    except json.JSONDecodeError:
        print("✗ Invalid JSON in configuration file")
        return False


def create_service_script():
    """Create a service script for running the monitor."""
    script_content = '''#!/bin/bash
# SPA News Monitor Service Script

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the monitor
python3 main.py
'''
    
    try:
        with open("run_monitor.sh", 'w') as f:
            f.write(script_content)
        
        # Make executable on Unix systems
        if os.name != 'nt':
            os.chmod("run_monitor.sh", 0o755)
        
        print("✓ Service script created: run_monitor.sh")
        return True
    except Exception as e:
        print(f"✗ Error creating service script: {e}")
        return False


def main():
    """Main setup function."""
    print("SPA News Monitor Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("✗ Python 3.7 or higher is required")
        sys.exit(1)
    
    print(f"✓ Python {sys.version.split()[0]} detected")
    
    # Install dependencies
    if not install_dependencies():
        print("Setup failed. Please install dependencies manually.")
        sys.exit(1)
    
    # Setup configuration
    if not setup_config():
        print("Setup failed. Please check your configuration.")
        sys.exit(1)
    
    # Validate configuration
    if not validate_config():
        print("Setup completed with warnings. Please review your configuration.")
    
    # Create service script
    create_service_script()
    
    print("\n" + "=" * 50)
    print("Setup completed successfully!")
    print("\nNext steps:")
    print("1. Review your configuration in config.json")
    print("2. Test the monitor: python main.py")
    print("3. For continuous monitoring, the script will run every 20 minutes")
    print("4. Check spa_news_monitor.log for detailed logs")
    print("\nPress Ctrl+C to stop the monitor when running.")


if __name__ == "__main__":
    main()