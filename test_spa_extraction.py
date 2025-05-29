#!/usr/bin/env python3
"""
Simple test script to verify SPA news extraction functionality.
"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import SPANewsMonitor
    import json
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)

def test_spa_extraction():
    """Test SPA news extraction without OpenAI API."""
    print("Testing SPA News Extraction...")
    print("=" * 50)
    
    try:
        # Create a minimal config for testing
        test_config = {
            'target_url': 'https://www.spa.gov.sa/en/news/latest-news?page=1',
            'database_path': 'test_news_monitor.db',
            'openai_api_key': 'test-key',  # Not used in this test
            'openai_model': 'gpt-4.1',
            'check_interval_minutes': 60,
            'email': {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'test@gmail.com',
                'password': 'test-password',
                'from_email': 'test@gmail.com',
                'to_email': 'test@gmail.com'
            }
        }
        
        # Save test config
        with open('test_config.json', 'w') as f:
            json.dump(test_config, f, indent=2)
        
        # Create monitor instance
        monitor = SPANewsMonitor('test_config.json')
        
        print("✓ Monitor initialized successfully")
        print(f"Target URL: {monitor.target_url}")
        print(f"Check interval: {monitor.check_interval} minutes")
        print()
        
        # Test news extraction
        print("Fetching news articles...")
        news_items = monitor.fetch_news_links()
        
        if news_items:
            print(f"✓ Successfully found {len(news_items)} news articles")
            print()
            print("Sample articles:")
            for i, item in enumerate(news_items[:5], 1):
                print(f"{i}. {item['title'][:80]}...")
                print(f"   URL: {item['url']}")
                print()
            
            # Test content extraction from first article
            if news_items:
                print("Testing content extraction from first article...")
                first_article = news_items[0]
                content = monitor.extract_article_content(first_article['url'])
                
                if content:
                    print(f"✓ Successfully extracted content ({len(content)} characters)")
                    print("Sample content:")
                    print(content[:200] + "..." if len(content) > 200 else content)
                else:
                    print("✗ Failed to extract content")
        else:
            print("✗ No news articles found")
            print("This might indicate:")
            print("- Website structure has changed")
            print("- Network connectivity issues")
            print("- Website blocking automated requests")
        
        # Clean up test files
        try:
            os.remove('test_config.json')
            if os.path.exists('test_news_monitor.db'):
                os.remove('test_news_monitor.db')
        except:
            pass
        
        return len(news_items) > 0
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_spa_extraction()
    print("\n" + "=" * 50)
    if success:
        print("✓ SPA extraction test PASSED")
        print("The monitor should be able to find and process news articles.")
    else:
        print("✗ SPA extraction test FAILED")
        print("Please check the issues mentioned above.")
    
    sys.exit(0 if success else 1)