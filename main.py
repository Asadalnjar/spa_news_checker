#!/usr/bin/env python3
"""
SPA News Monitor with Grammar Check Integration
Monitors SPA news website, checks grammar via ChatGPT API, and sends email alerts.
Cloud-ready version with environment variable support for Render deployment.
"""

import os
import sys
import time
import json
import sqlite3
import logging
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

from openai import OpenAI
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import health check server for cloud deployment
try:
    from health_check import run_health_server_background
    HEALTH_CHECK_AVAILABLE = True
except ImportError:
    HEALTH_CHECK_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spa_news_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SPANewsMonitor:
    """Main class for SPA news monitoring and grammar checking."""
    
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the news monitor with configuration."""
        self.config = self.load_config(config_file)
        self.db_path = self.config.get('database_path', 'news_monitor.db')
        self.base_url = 'https://www.spa.gov.sa'
        self.target_url = self.config['target_url']
        self.check_interval = self.config.get('check_interval_minutes', 20)
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=self.config['openai_api_key'])
        
        # Initialize database
        self.init_database()
        
        # Email configuration
        self.smtp_config = self.config['email']
        
        logger.info("SPA News Monitor initialized successfully")
        logger.info(f"Target URL: {self.target_url}")
        logger.info(f"Check interval: {self.check_interval} minutes")
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file or environment variables."""
        # First try to load from environment variables (for cloud deployment)
        if self.load_from_env():
            logger.info("Configuration loaded from environment variables")
            return self.get_env_config()
        
        # Fallback to JSON file (for local development)
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Configuration loaded from {config_file}")
                return config
            else:
                logger.error(f"Configuration file {config_file} not found and no environment variables set")
                sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)
    
    def load_from_env(self) -> bool:
        """Check if all required environment variables are set."""
        required_env_vars = [
            'OPENAI_API_KEY',
            'EMAIL_USERNAME',
            'EMAIL_PASSWORD',
            'EMAIL_FROM',
            'EMAIL_TO'
        ]
        return all(os.getenv(var) for var in required_env_vars)
    
    def get_env_config(self) -> Dict:
        """Get configuration from environment variables."""
        return {
            'target_url': os.getenv('TARGET_URL', 'https://www.youm7.com/Section/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1-%D8%B9%D8%A7%D8%AC%D9%84%D8%A9/65/1'),
            'database_path': os.getenv('DATABASE_PATH', 'news_monitor.db'),
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'openai_model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            'check_interval_minutes': int(os.getenv('CHECK_INTERVAL_MINUTES', '60')),
            'email': {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'username': os.getenv('EMAIL_USERNAME'),
                'password': os.getenv('EMAIL_PASSWORD'),
                'from_email': os.getenv('EMAIL_FROM'),
                'to_email': os.getenv('EMAIL_TO')
            }
        }
    
    def init_database(self):
        """Initialize SQLite database for tracking processed articles."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    grammar_status TEXT,
                    mistakes TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            sys.exit(1)
    
    def is_article_processed(self, url: str) -> bool:
        """Check if an article has already been processed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT 1 FROM processed_articles WHERE url = ?', (url,))
            result = cursor.fetchone()
            
            conn.close()
            return result is not None
        except sqlite3.Error as e:
            logger.error(f"Database query error: {e}")
            return False
    
    def mark_article_processed(self, url: str, title: str, status: str, mistakes: str = None):
        """Mark an article as processed in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO processed_articles 
                (url, title, grammar_status, mistakes) 
                VALUES (?, ?, ?, ?)
            ''', (url, title, status, mistakes))
            
            conn.commit()
            conn.close()
            logger.info(f"Article marked as processed: {url}")
        except sqlite3.Error as e:
            logger.error(f"Database insert error: {e}")
    
    def fetch_news_links(self) -> List[Dict[str, str]]:
        """Fetch news article links from the target page."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(self.target_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find news article links - SPA specific selectors
            news_items = []
            
            # SPA website specific selectors
            spa_selectors = [
                'a[href*="/viewfullstory/"]',  # SPA specific story links
                'a[href*="/news/"]',           # General news links
                '.news-item a',                # News item containers
                '.article-title a',            # Article title links
                '.story-link',                 # Story links
                'h3 a',                        # Headlines in h3 tags
                'h2 a',                        # Headlines in h2 tags
                '.title a',                    # Title links
                'a[href*="story"]',            # Any link containing "story"
                'a[href*="article"]'           # Any link containing "article"
            ]
            
            # Try each selector
            for selector in spa_selectors:
                links = soup.select(selector)
                logger.info(f"Selector '{selector}': Found {len(links)} links")
                
                if links:
                    for link in links:
                        href = link.get('href')
                        if href:
                            # Convert relative URLs to absolute
                            full_url = urljoin(self.base_url, href)
                            title = link.get_text(strip=True) or link.get('title', 'No title')
                            
                            # Filter out empty titles and non-news links
                            if title and len(title) > 10 and 'news' in full_url.lower():
                                news_items.append({
                                    'url': full_url,
                                    'title': title
                                })
            
            # If no specific selectors work, try to find any links that might be news
            if not news_items:
                logger.info("No items found with specific selectors, trying general approach...")
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    # Look for news-related URLs
                    if any(keyword in href.lower() for keyword in ['news', 'story', 'article', 'viewfullstory']):
                        full_url = urljoin(self.base_url, href)
                        if title and len(title) > 10:
                            news_items.append({
                                'url': full_url,
                                'title': title
                            })
            
            # Remove duplicates
            seen_urls = set()
            unique_items = []
            for item in news_items:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_items.append(item)
            
            logger.info(f"Found {len(unique_items)} news articles")
            
            # Log first few items for debugging
            for i, item in enumerate(unique_items[:3]):
                logger.info(f"Article {i+1}: {item['title'][:50]}... - {item['url']}")
            
            return unique_items
            
        except requests.RequestException as e:
            logger.error(f"Error fetching news links: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in fetch_news_links: {e}")
            return []
    
    def extract_article_content(self, url: str) -> Optional[str]:
        """Extract the main content from a news article."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'menu', 'form']):
                element.decompose()
            
            # SPA specific selectors for article content
            spa_content_selectors = [
                '.story-content',
                '.article-content',
                '.news-content',
                '.content-body',
                '.story-body',
                '.article-body',
                '.news-body',
                '.main-content',
                '.post-content',
                'article .content',
                '#content',
                '.text-content',
                '.story-text'
            ]
            
            content = None
            for selector in spa_content_selectors:
                element = soup.select_one(selector)
                if element:
                    content = element.get_text(strip=True)
                    logger.info(f"Content extracted using selector: {selector}")
                    break
            
            # Fallback: try to find content in div with specific classes
            if not content:
                content_divs = soup.find_all('div', class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['content', 'story', 'article', 'text', 'body']
                ))
                if content_divs:
                    # Get the div with most text content
                    best_div = max(content_divs, key=lambda div: len(div.get_text(strip=True)))
                    content = best_div.get_text(strip=True)
                    logger.info("Content extracted from content div")
            
            # Fallback: try to find the largest text block from paragraphs
            if not content:
                paragraphs = soup.find_all('p')
                if paragraphs:
                    # Filter paragraphs with meaningful content
                    meaningful_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                    if meaningful_paragraphs:
                        content = ' '.join(meaningful_paragraphs)
                        logger.info("Content extracted from paragraphs")
            
            # Final fallback: get all text but filter out navigation and menu items
            if not content:
                # Remove common navigation elements
                for nav_element in soup.find_all(['nav', 'menu', 'ul', 'ol'], class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['nav', 'menu', 'breadcrumb', 'sidebar']
                )):
                    nav_element.decompose()
                
                content = soup.get_text(strip=True)
                logger.info("Content extracted using fallback method")
            
            # Clean up content
            if content:
                # Remove extra whitespace and line breaks
                content = ' '.join(content.split())
                
                # Remove common unwanted phrases
                unwanted_phrases = [
                    'Skip to main content',
                    'Cookie Policy',
                    'Privacy Policy',
                    'Terms of Service',
                    'Subscribe to newsletter',
                    'Follow us on',
                    'Share this article'
                ]
                
                for phrase in unwanted_phrases:
                    content = content.replace(phrase, '')
                
                # Limit content length for API efficiency
                if len(content) > 4000:
                    content = content[:4000] + "..."
                
                logger.info(f"Extracted content length: {len(content)} characters")
                return content
            else:
                logger.warning("No content could be extracted")
                return None
            
        except requests.RequestException as e:
            logger.error(f"Error fetching article content from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting content from {url}: {e}")
            return None
    
    def check_grammar_with_chatgpt(self, content: str) -> Tuple[str, str]:
        """Check grammar and spelling using ChatGPT API."""
        try:
            prompt = (
                "Check grammar and spelling mistakes of the news item. "
                "If there are no mistakes, reply: OK. "
                "If there are any mistakes, reply: Caution, and list all found mistakes."
            )
            
            response = self.openai_client.responses.create(
                model=self.config.get('openai_model', 'gpt-4.1'),
                input=f"{prompt}\n\nContent to check: {content}"
            )
            
            result = response.output_text.strip()
            
            if result.upper().startswith('OK'):
                return 'OK', ''
            elif result.upper().startswith('CAUTION'):
                mistakes = result[8:].strip() if len(result) > 8 else result
                return 'Caution', mistakes
            else:
                # Parse response to determine status
                if 'no mistakes' in result.lower() or 'no errors' in result.lower():
                    return 'OK', ''
                else:
                    return 'Caution', result
                    
        except Exception as e:
            logger.error(f"Error checking grammar with ChatGPT: {e}")
            return 'Error', f"API Error: {str(e)}"
    
    def send_email_notification(self, news_index: int, article_url: str, title: str, status: str, mistakes: str = None):
        """Send email notification based on grammar check results."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = self.smtp_config['to_email']
            msg['Subject'] = f"SPA News Grammar Check - News #{news_index} - {status}"
            
            # Create email body
            body = f"""
News #{news_index}
Title: {title}
Article Link: {article_url}
Status: {status}
"""
            
            if status == 'Caution' and mistakes:
                body += f"\nMistakes Found:\n{mistakes}"
            
            body += f"\n\nChecked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port'])
            server.starttls()
            server.login(self.smtp_config['username'], self.smtp_config['password'])
            
            text = msg.as_string()
            server.sendmail(self.smtp_config['from_email'], self.smtp_config['to_email'], text)
            server.quit()
            
            logger.info(f"Email notification sent for News #{news_index} - Status: {status}")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    def process_news_articles(self):
        """Main method to process news articles."""
        logger.info("Starting news article processing...")
        
        # Fetch news links
        news_items = self.fetch_news_links()
        
        if not news_items:
            logger.warning("No news articles found")
            return
        
        new_articles_count = 0
        
        for index, item in enumerate(news_items, 1):
            url = item['url']
            title = item['title']
            
            # Skip if already processed
            if self.is_article_processed(url):
                logger.info(f"Article already processed: {title}")
                continue
            
            logger.info(f"Processing new article #{index}: {title}")
            
            # Extract content
            content = self.extract_article_content(url)
            if not content:
                logger.warning(f"Could not extract content from: {url}")
                continue
            
            # Check grammar
            status, mistakes = self.check_grammar_with_chatgpt(content)
            
            # Mark as processed
            self.mark_article_processed(url, title, status, mistakes)
            
            # Send email notification
            self.send_email_notification(index, url, title, status, mistakes)
            
            new_articles_count += 1
            
            # Add delay between API calls to avoid rate limiting
            time.sleep(2)
        
        logger.info(f"Processing completed. {new_articles_count} new articles processed.")
    
    def run_scheduler(self):
        """Run the scheduler for continuous monitoring."""
        scheduler = BlockingScheduler()
        
        # Schedule the job to run at specified interval
        scheduler.add_job(
            func=self.process_news_articles,
            trigger=IntervalTrigger(minutes=self.check_interval),
            id='news_monitor_job',
            name='SPA News Monitor Job',
            replace_existing=True
        )
        
        logger.info(f"Scheduler started. Monitoring will run every {self.check_interval} minutes.")
        logger.info("Press Ctrl+C to stop the monitor.")
        
        try:
            # Run initial check
            self.process_news_articles()
            
            # Start scheduler
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            scheduler.shutdown()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            scheduler.shutdown()


def main():
    """Main entry point."""
    try:
        monitor = SPANewsMonitor()
        monitor.run_scheduler()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()