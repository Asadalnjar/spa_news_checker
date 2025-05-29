#!/usr/bin/env python3
"""
Test script to verify Selenium setup and Chrome WebDriver functionality.
"""

import sys
import os

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    print("✓ All Selenium imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Please install: pip install selenium webdriver-manager")
    sys.exit(1)

def test_selenium_setup():
    """Test basic Selenium functionality."""
    print("Testing Selenium WebDriver setup...")
    print("=" * 50)
    
    driver = None
    try:
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        print("Creating Chrome WebDriver...")
        
        # Try to create WebDriver
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✓ Chrome WebDriver created successfully")
        except Exception as e:
            print(f"✗ Error creating WebDriver: {e}")
            return False
        
        # Test basic navigation
        print("Testing navigation to Google...")
        driver.get("https://www.google.com")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        title = driver.title
        print(f"✓ Page loaded successfully. Title: {title}")
        
        # Test SPA website
        print("Testing SPA website access...")
        spa_url = "https://www.spa.gov.sa/en/news/latest-news?page=1"
        driver.get(spa_url)
        
        # Wait for page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        spa_title = driver.title
        print(f"✓ SPA website loaded. Title: {spa_title}")
        
        # Try to find some links
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"✓ Found {len(links)} links on SPA page")
        
        # Look for news-related links
        news_links = []
        for link in links[:20]:  # Check first 20 links
            try:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and any(keyword in href.lower() for keyword in ['news', 'story', 'article', 'viewfullstory']):
                    news_links.append((href, text[:50]))
            except:
                continue
        
        print(f"✓ Found {len(news_links)} potential news links")
        for i, (url, text) in enumerate(news_links[:3]):
            print(f"  {i+1}. {text}... - {url}")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
                print("✓ WebDriver closed successfully")
            except:
                pass

def main():
    """Main test function."""
    success = test_selenium_setup()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ Selenium setup test PASSED")
        print("Chrome WebDriver is working correctly.")
        print("The SPA news monitor should be able to extract content.")
    else:
        print("✗ Selenium setup test FAILED")
        print("Please check Chrome installation and dependencies.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)