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

import openai
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
        openai.api_key = self.config['openai_api_key']
        
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
            'target_url': os.getenv('TARGET_URL', 'https://www.spa.gov.sa/en/news/latest-news?page=4'),
            'database_path': os.getenv('DATABASE_PATH', 'news_monitor.db'),
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'openai_model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            'check_interval_minutes': int(os.getenv('CHECK_INTERVAL_MINUTES', '20')),
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.target_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find news article links - adjust selectors based on actual HTML structure
            news_items = []
            
            # Common selectors for news articles (may need adjustment)
            article_selectors = [
                'article a[href*="/news/"]',
                '.news-item a',
                '.article-link',
                'a[href*="/viewfullstory/"]',
                '.news-list a'
            ]
            
            for selector in article_selectors:
                links = soup.select(selector)
                if links:
                    for link in links:
                        href = link.get('href')
                        if href:
                            # Convert relative URLs to absolute
                            full_url = urljoin(self.base_url, href)
                            title = link.get_text(strip=True) or link.get('title', 'No title')
                            
                            news_items.append({
                                'url': full_url,
                                'title': title
                            })
                    break  # Use first successful selector
            
            # Remove duplicates
            seen_urls = set()
            unique_items = []
            for item in news_items:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_items.append(item)
            
            logger.info(f"Found {len(unique_items)} news articles")
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Common selectors for article content
            content_selectors = [
                '.article-content',
                '.news-content',
                '.story-content',
                '.post-content',
                'article .content',
                '.main-content',
                '#content'
            ]
            
            content = None
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    content = element.get_text(strip=True)
                    break
            
            # Fallback: try to find the largest text block
            if not content:
                paragraphs = soup.find_all('p')
                if paragraphs:
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # Final fallback: get all text
            if not content:
                content = soup.get_text(strip=True)
            
            # Clean up content
            if content:
                # Remove extra whitespace
                content = ' '.join(content.split())
                # Limit content length for API efficiency
                if len(content) > 4000:
                    content = content[:4000] + "..."
            
            return content
            
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
            
            response = openai.ChatCompletion.create(
                model=self.config.get('openai_model', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
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