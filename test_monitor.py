#!/usr/bin/env python3
"""
Test script for SPA News Monitor
Tests individual components and overall functionality.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import SPANewsMonitor
    from openai import OpenAI
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestSPANewsMonitor:
    """Test class for SPA News Monitor functionality."""
    
    def __init__(self):
        self.config_file = 'config.json'
        self.test_results = []
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test results."""
        status = "PASS" if passed else "FAIL"
        result = f"[{status}] {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))
    
    def test_config_file(self):
        """Test configuration file loading."""
        try:
            if not os.path.exists(self.config_file):
                self.log_test("Config File Exists", False, "config.json not found")
                return False
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            required_keys = ['target_url', 'openai_api_key', 'email']
            missing_keys = [key for key in required_keys if key not in config]
            
            if missing_keys:
                self.log_test("Config File Structure", False, f"Missing keys: {missing_keys}")
                return False
            
            self.log_test("Config File Loading", True)
            return True
            
        except json.JSONDecodeError:
            self.log_test("Config File Loading", False, "Invalid JSON format")
            return False
        except Exception as e:
            self.log_test("Config File Loading", False, str(e))
            return False
    
    def test_dependencies(self):
        """Test if all required dependencies are installed."""
        dependencies = [
            ('requests', 'requests'),
            ('beautifulsoup4', 'bs4'),
            ('openai', 'openai'),
            ('APScheduler', 'apscheduler'),
        ]
        
        all_passed = True
        for dep_name, import_name in dependencies:
            try:
                __import__(import_name)
                self.log_test(f"Dependency: {dep_name}", True)
            except ImportError:
                self.log_test(f"Dependency: {dep_name}", False, "Not installed")
                all_passed = False
        
        return all_passed
    
    def test_target_website(self):
        """Test if the target website is accessible."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            target_url = config['target_url']
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(target_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.log_test("Target Website Access", True, f"Status: {response.status_code}")
                
                # Test if we can parse the content
                soup = BeautifulSoup(response.content, 'html.parser')
                if soup.find('html'):
                    self.log_test("Website Content Parsing", True)
                    return True
                else:
                    self.log_test("Website Content Parsing", False, "No HTML content found")
                    return False
            else:
                self.log_test("Target Website Access", False, f"Status: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            self.log_test("Target Website Access", False, str(e))
            return False
        except Exception as e:
            self.log_test("Target Website Access", False, f"Unexpected error: {e}")
            return False
    
    def test_openai_api(self):
        """Test OpenAI API connectivity."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            api_key = config['openai_api_key']
            
            if not api_key or api_key == 'YOUR_OPENAI_API_KEY_HERE':
                self.log_test("OpenAI API Key", False, "API key not configured")
                return False
            
            client = OpenAI(api_key=api_key)
            
            # Test with a simple request
            response = client.responses.create(
                model=config.get('openai_model', 'gpt-4.1'),
                input="Test message. Reply with 'OK' if you receive this."
            )
            
            if response.output_text:
                self.log_test("OpenAI API Connection", True)
                return True
            else:
                self.log_test("OpenAI API Connection", False, "No response content")
                return False
                
        except Exception as e:
            self.log_test("OpenAI API Connection", False, str(e))
            return False
    
    def test_email_config(self):
        """Test email configuration (without sending)."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            email_config = config.get('email', {})
            required_fields = ['smtp_server', 'smtp_port', 'username', 'password', 'from_email', 'to_email']
            
            missing_fields = [field for field in required_fields if not email_config.get(field)]
            
            if missing_fields:
                self.log_test("Email Configuration", False, f"Missing fields: {missing_fields}")
                return False
            
            self.log_test("Email Configuration", True)
            return True
            
        except Exception as e:
            self.log_test("Email Configuration", False, str(e))
            return False
    
    def test_database_creation(self):
        """Test database initialization."""
        try:
            # Create a test monitor instance
            monitor = SPANewsMonitor()
            
            # Check if database file exists
            if os.path.exists(monitor.db_path):
                self.log_test("Database Creation", True)
                
                # Test database structure
                conn = sqlite3.connect(monitor.db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_articles'")
                table_exists = cursor.fetchone() is not None
                
                conn.close()
                
                if table_exists:
                    self.log_test("Database Structure", True)
                    return True
                else:
                    self.log_test("Database Structure", False, "Table not created")
                    return False
            else:
                self.log_test("Database Creation", False, "Database file not created")
                return False
                
        except Exception as e:
            self.log_test("Database Creation", False, str(e))
            return False
    
    def test_news_scraping(self):
        """Test news article scraping functionality."""
        try:
            monitor = SPANewsMonitor()
            news_items = monitor.fetch_news_links()
            
            if news_items:
                self.log_test("News Scraping", True, f"Found {len(news_items)} articles")
                
                # Test content extraction from first article
                if news_items:
                    first_article = news_items[0]
                    content = monitor.extract_article_content(first_article['url'])
                    
                    if content and len(content) > 50:
                        self.log_test("Content Extraction", True, f"Extracted {len(content)} characters")
                        return True
                    else:
                        self.log_test("Content Extraction", False, "No meaningful content extracted")
                        return False
            else:
                self.log_test("News Scraping", False, "No articles found")
                return False
                
        except Exception as e:
            self.log_test("News Scraping", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests and provide summary."""
        print("SPA News Monitor - Test Suite")
        print("=" * 50)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run tests
        tests = [
            self.test_dependencies,
            self.test_config_file,
            self.test_target_website,
            self.test_database_creation,
            self.test_email_config,
            self.test_openai_api,
            self.test_news_scraping,
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
                self.log_test(test_name, False, f"Test error: {e}")
            print()
        
        # Summary
        print("=" * 50)
        print("Test Summary:")
        
        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ All tests passed! The monitor is ready to run.")
            print("Run 'python main.py' to start monitoring.")
        else:
            print(f"\n✗ {total - passed} test(s) failed. Please fix the issues before running the monitor.")
            print("\nFailed tests:")
            for test_name, result, message in self.test_results:
                if not result:
                    print(f"  - {test_name}: {message}")
        
        return passed == total


def main():
    """Main test function."""
    tester = TestSPANewsMonitor()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()