#!/usr/bin/env python3
"""
Test script to analyze SPA website structure and fix scraping issues.
"""

import requests
from bs4 import BeautifulSoup
import json

def test_spa_scraping():
    """Test scraping the SPA news website."""
    url = "https://www.youm7.com/Section/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1-%D8%B9%D8%A7%D8%AC%D9%84%D8%A9/65/1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"Response status: {response.status_code}")
        print(f"Content length: {len(response.content)}")
        
        # Look for common news article patterns
        selectors_to_test = [
            'article a[href*="/news/"]',
            '.news-item a',
            '.article-link',
            'a[href*="/viewfullstory/"]',
            '.news-list a',
            'a[href*="/news/"]',
            '.news a',
            '.article a',
            'a[href*="news"]',
            'a[href*="story"]'
        ]
        
        print("\n=== Testing different selectors ===")
        for selector in selectors_to_test:
            links = soup.select(selector)
            print(f"Selector '{selector}': Found {len(links)} links")
            if links:
                for i, link in enumerate(links[:3]):  # Show first 3
                    href = link.get('href', 'No href')
                    text = link.get_text(strip=True)[:50]
                    print(f"  {i+1}. {href} - {text}")
        
        # Look for any links that might be news articles
        print("\n=== All links analysis ===")
        all_links = soup.find_all('a', href=True)
        news_links = []
        
        for link in all_links:
            href = link.get('href', '')
            if any(keyword in href.lower() for keyword in ['news', 'story', 'article']):
                news_links.append({
                    'href': href,
                    'text': link.get_text(strip=True)[:100]
                })
        
        print(f"Found {len(news_links)} potential news links")
        for i, link in enumerate(news_links[:10]):  # Show first 10
            print(f"  {i+1}. {link['href']} - {link['text']}")
        
        # Save HTML for manual inspection
        with open('spa_page_source.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"\nPage source saved to spa_page_source.html")
        
        return len(news_links)
        
    except Exception as e:
        print(f"Error: {e}")
        return 0

if __name__ == "__main__":
    test_spa_scraping()