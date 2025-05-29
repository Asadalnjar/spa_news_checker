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

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

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
    
    def create_webdriver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver for cloud deployment."""
        try:
            chrome_options = Options()
            
            # Essential options for cloud deployment
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript-harmony-shipping')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-crash-reporter')
            chrome_options.add_argument('--disable-oopr-debug-crash-dump')
            chrome_options.add_argument('--no-crash-upload')
            chrome_options.add_argument('--disable-low-res-tiling')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--remote-debugging-port=9222')
            
            # User agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Try multiple approaches to create WebDriver
            driver = None
            
            # Approach 1: Try system Chrome with specific binary location
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
                '/opt/google/chrome/chrome',
                '/opt/google/chrome/google-chrome'
            ]
            
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    try:
                        logger.info(f"Trying Chrome binary: {chrome_path}")
                        chrome_options.binary_location = chrome_path
                        
                        # Try with system chromedriver first
                        try:
                            service = Service('/usr/bin/chromedriver')
                            driver = webdriver.Chrome(service=service, options=chrome_options)
                            logger.info(f"WebDriver created with system chromedriver and {chrome_path}")
                            break
                        except:
                            # Fallback to ChromeDriverManager
                            service = Service(ChromeDriverManager().install())
                            driver = webdriver.Chrome(service=service, options=chrome_options)
                            logger.info(f"WebDriver created with ChromeDriverManager and {chrome_path}")
                            break
                    except Exception as e:
                        logger.debug(f"Failed with {chrome_path}: {e}")
                        continue
            
            # Approach 2: If no system Chrome found, try ChromeDriverManager only
            if not driver:
                try:
                    logger.info("Trying ChromeDriverManager without specific binary")
                    # Create new options without binary_location
                    fallback_options = Options()
                    for arg in chrome_options.arguments:
                        fallback_options.add_argument(arg)
                    
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=fallback_options)
                    logger.info("WebDriver created with ChromeDriverManager")
                except Exception as e:
                    logger.error(f"ChromeDriverManager failed: {e}")
                    raise
            
            if driver:
                driver.set_page_load_timeout(30)
                driver.implicitly_wait(10)
                logger.info("WebDriver configured successfully")
                return driver
            else:
                raise Exception("Failed to create WebDriver with any method")
                
        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            # Fallback: try to use requests instead
            logger.info("WebDriver failed, will fallback to requests method")
            raise
    
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
            'target_url': os.getenv('TARGET_URL', 'https://www.spa.gov.sa/en/news/latest-news?page=1'),
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
    
    def fetch_news_links_with_requests(self) -> List[Dict[str, str]]:
        """Fallback method to fetch news links using requests."""
        try:
            logger.info("Using requests fallback method...")
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
            
            # Find news article links
            news_items = []
            
            # Try various selectors - start with most general
            selectors = [
                'a',  # All links first
                'a[href*="/viewfullstory/"]',
                'a[href*="/news/"]',
                '.news-item a',
                '.article-title a',
                'h3 a',
                'h2 a',
                'h1 a',
                '.title a',
                'a[href*="story"]',
                'a[href*="article"]'
            ]
            
            # First, let's see what we can find
            all_links = soup.find_all('a', href=True)
            logger.info(f"Total links found on page: {len(all_links)}")
            
            # Log some sample links for debugging
            sample_links = []
            for i, link in enumerate(all_links[:10]):
                href = link.get('href', '')
                text = link.get_text(strip=True)[:50]
                sample_links.append(f"{i+1}. {href} - {text}")
            
            if sample_links:
                logger.info("Sample links found:")
                for sample in sample_links:
                    logger.info(f"  {sample}")
            
            # Now try to find news-related links
            for link in all_links:
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                if href and title:
                    # Convert relative URLs to absolute
                    full_url = urljoin(self.base_url, href)
                    
                    # Look for any links that might be news articles
                    # Be more permissive in filtering
                    if (len(title) > 5 and
                        (any(keyword in href.lower() for keyword in ['news', 'story', 'article', 'viewfullstory', 'spa.gov.sa']) or
                         any(keyword in title.lower() for keyword in ['news', 'report', 'statement', 'announcement']))):
                        news_items.append({
                            'url': full_url,
                            'title': title
                        })
            
            # If still no items, try the specific selectors
            if not news_items:
                for selector in selectors[1:]:  # Skip 'a' since we already tried all links
                    links = soup.select(selector)
                    logger.info(f"Requests selector '{selector}': Found {len(links)} links")
                    
                    if links:
                        for link in links:
                            href = link.get('href')
                            if href:
                                full_url = urljoin(self.base_url, href)
                                title = link.get_text(strip=True) or link.get('title', 'No title')
                                
                                if title and len(title) > 5:
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
            
            logger.info(f"Requests method found {len(unique_items)} news articles")
            return unique_items
            
        except Exception as e:
            logger.error(f"Requests fallback failed: {e}")
            return []
    
    def fetch_news_links(self) -> List[Dict[str, str]]:
        """Fetch news article links from the target page using Selenium with requests fallback."""
        # Try Selenium first
        driver = None
        try:
            logger.info("Attempting Selenium method for news extraction...")
            driver = self.create_webdriver()
            
            logger.info(f"Loading page: {self.target_url}")
            driver.get(self.target_url)
            
            # Wait for page to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(5)
            
            # Get page source after JavaScript execution
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            logger.info("Page loaded successfully, extracting news links...")
            
            # Find news article links - SPA specific selectors
            news_items = []
            
            # SPA website specific selectors (updated for dynamic content)
            spa_selectors = [
                'a[href*="/viewfullstory/"]',  # SPA specific story links
                'a[href*="/news/"]',           # General news links
                '.news-item a',                # News item containers
                '.article-title a',            # Article title links
                '.story-link',                 # Story links
                'h3 a',                        # Headlines in h3 tags
                'h2 a',                        # Headlines in h2 tags
                'h1 a',                        # Headlines in h1 tags
                '.title a',                    # Title links
                '.headline a',                 # Headline links
                '.news-title a',               # News title links
                'a[href*="story"]',            # Any link containing "story"
                'a[href*="article"]',          # Any link containing "article"
                '.card a',                     # Card-based layouts
                '.item a',                     # Item-based layouts
                'article a'                    # Article elements
            ]
            
            # Try each selector
            for selector in spa_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Selector '{selector}': Found {len(elements)} elements")
                    
                    if elements:
                        for element in elements:
                            try:
                                href = element.get_attribute('href')
                                title = element.text.strip() or element.get_attribute('title') or 'No title'
                                
                                if href and title:
                                    # Convert relative URLs to absolute
                                    full_url = urljoin(self.base_url, href)
                                    
                                    # Filter out empty titles and non-news links
                                    if len(title) > 10 and any(keyword in full_url.lower() for keyword in ['news', 'story', 'article', 'viewfullstory']):
                                        news_items.append({
                                            'url': full_url,
                                            'title': title
                                        })
                            except Exception as e:
                                logger.debug(f"Error processing element: {e}")
                                continue
                except Exception as e:
                    logger.debug(f"Error with selector '{selector}': {e}")
                    continue
            
            # If no specific selectors work, try to find any links that might be news
            if not news_items:
                logger.info("No items found with specific selectors, trying general approach...")
                try:
                    all_links = driver.find_elements(By.TAG_NAME, "a")
                    logger.info(f"Found {len(all_links)} total links")
                    
                    for link in all_links:
                        try:
                            href = link.get_attribute('href') or ''
                            title = link.text.strip()
                            
                            # Look for news-related URLs
                            if href and title and any(keyword in href.lower() for keyword in ['news', 'story', 'article', 'viewfullstory']):
                                full_url = urljoin(self.base_url, href)
                                if len(title) > 10:
                                    news_items.append({
                                        'url': full_url,
                                        'title': title
                                    })
                        except Exception as e:
                            logger.debug(f"Error processing link: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error in general approach: {e}")
            
            # Remove duplicates
            seen_urls = set()
            unique_items = []
            for item in news_items:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_items.append(item)
            
            logger.info(f"Found {len(unique_items)} unique news articles")
            
            # Log first few items for debugging
            for i, item in enumerate(unique_items[:3]):
                logger.info(f"Article {i+1}: {item['title'][:50]}... - {item['url']}")
            
            return unique_items
            
        except TimeoutException:
            logger.error("Timeout waiting for page to load")
            logger.info("Falling back to requests method...")
            return self.fetch_news_links_with_requests()
        except WebDriverException as e:
            logger.error(f"WebDriver error: {e}")
            logger.info("Falling back to requests method...")
            return self.fetch_news_links_with_requests()
        except Exception as e:
            logger.error(f"Selenium method failed: {e}")
            logger.info("Falling back to requests method...")
            return self.fetch_news_links_with_requests()
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("WebDriver closed successfully")
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {e}")
    
    def extract_article_content(self, url: str) -> Optional[str]:
        """Extract the main content from a news article using Selenium."""
        driver = None
        try:
            logger.info(f"Extracting content from: {url}")
            driver = self.create_webdriver()
            
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Get page source after JavaScript execution
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
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
                '.story-text',
                '.article-text',
                '.news-text'
            ]
            
            content = None
            
            # Try Selenium-based extraction first
            try:
                for selector in spa_content_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            content = elements[0].text.strip()
                            if content and len(content) > 50:
                                logger.info(f"Content extracted using Selenium selector: {selector}")
                                break
                    except Exception as e:
                        logger.debug(f"Error with Selenium selector '{selector}': {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error in Selenium extraction: {e}")
            
            # Fallback to BeautifulSoup extraction
            if not content:
                for selector in spa_content_selectors:
                    element = soup.select_one(selector)
                    if element:
                        content = element.get_text(strip=True)
                        if content and len(content) > 50:
                            logger.info(f"Content extracted using BeautifulSoup selector: {selector}")
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
                    if content and len(content) > 50:
                        logger.info("Content extracted from content div")
            
            # Fallback: try to find the largest text block from paragraphs
            if not content:
                paragraphs = soup.find_all('p')
                if paragraphs:
                    # Filter paragraphs with meaningful content
                    meaningful_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                    if meaningful_paragraphs:
                        content = ' '.join(meaningful_paragraphs)
                        if content and len(content) > 50:
                            logger.info("Content extracted from paragraphs")
            
            # Final fallback: get all text but filter out navigation and menu items
            if not content:
                # Remove common navigation elements
                for nav_element in soup.find_all(['nav', 'menu', 'ul', 'ol'], class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['nav', 'menu', 'breadcrumb', 'sidebar']
                )):
                    nav_element.decompose()
                
                content = soup.get_text(strip=True)
                if content and len(content) > 50:
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
                    'Share this article',
                    'Advertisement',
                    'إعلان',
                    'تابعنا على',
                    'شارك المقال'
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
            
        except TimeoutException:
            logger.error(f"Timeout extracting content from {url}")
            return None
        except WebDriverException as e:
            logger.error(f"WebDriver error extracting content from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting content from {url}: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {e}")
    
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
