import requests
from bs4 import BeautifulSoup
import openai
import smtplib
from email.message import EmailMessage
import sqlite3
import schedule
import time
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("✅ main.py started", flush=True)

# === إعداد المفاتيح والبيئة ===
SPA_URL = "https://www.spa.gov.sa/en/news/latest-news?page=1"
openai.api_key = os.environ["OPENAI_API_KEY"]
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
DB_FILE = "visited_news.db"

# الكلمات والعبارات المستبعدة من الفحص
EXCLUDED_WORDS = [
    "January", "February", "March", "April", "May", "June", 
    "July", "August", "September", "October", "November", "December",
    "Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Awwal",
    "Jumada al-Thani", "Rajab", "Sha'ban", "Ramadan", "Shawwal",
    "Dhu al-Qi'dah", "Dhu al-Hijjah",
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "The Saudi Press Agency (SPA), established in 1971, is a prime reference for those interested in local news and events. The agency provides accurate and real-time media content in several languages. It operates ​​according to professional best practices and makes use of the latest effective communication techniques. SPA seeks to be an influential voice of the Kingdom of Saudi Arabia in the Arab and Islamic worlds, as well as globally.",
    "Agency services", "Tenders", "Contact", "Privacy policy", 
    "Terms-and-Conditions", "Public services", "Private Sector Feedback Platform", 
    "Public Consultation Platform"
]

# ✅ العبارات التي سيتم تجاهلها في النتائج
IGNORE_PHRASES = [
    "All rights reserved to the Saudi Press Agency"
]

# ✅ أنماط المشكلات التافهة
TRIVIAL_PATTERNS = [
    r"\b(capitalize|capitalized)\b",
    r"\b(add|missing) comma\b",
    r"\bextra space\b",
    r"\bpunctuation\b",
    r"\bquotation marks\b",
    r"\bspacing\b",
    r"\bredundant\b",
    r"\bOK to leave as is\b"
]

# === قاعدة البيانات ===
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def is_visited(url):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM visited WHERE url = ?", (url,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_visited(url):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO visited (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

# === جلب روابط الأخبار ===
def get_latest_news_urls():
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.binary_location = "/usr/bin/chromium"
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(SPA_URL)
        time.sleep(7)

        elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='/en/N']")
        urls = []
        for elem in elements:
            href = elem.get_attribute("href")
            if href:
                full_url = href if href.startswith("http") else "https://www.spa.gov.sa" + href
                urls.append(full_url)

        driver.quit()
        print(f"✅ [Selenium] Found {len(urls)} news URLs", flush=True)
        return urls
    except Exception as e:
        print(f"❌ Selenium error: {e}", flush=True)
        return []

# === استخراج محتوى الخبر ===
def extract_news_content(url):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.binary_location = "/usr/bin/chromium"

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        possible_selectors = [
            "div.singleNewsText",
            "div.newsContent",
            "section.singleNewsText",
            "article.singleNewsText",
            "div.news_body",
            "div.article-text",
            "div.articleBody"
        ]
        article = None
        for selector in possible_selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                article = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue

        if not article:
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
        else:
            paragraphs = article.find_elements(By.TAG_NAME, "p")

        seen = set()
        content_lines = []
        for p in paragraphs:
            text = p.text.strip()
            if len(text.split()) < 4:
                continue
            if text and text not in seen:
                seen.add(text)
                content_lines.append(text)

        content = "\n".join(content_lines)
        driver.quit()
        return content

    except Exception as e:
        print(f"❌ Selenium error while extracting content: {e}", flush=True)
        return ""

# === الفلاتر للمشاكل التافهة ===
def is_false_positive_grammar(result):
    if not result.strip() or result.strip().lower() == "ok":
        return True

    lines = [line for line in result.splitlines() if line.strip()]
    if not lines:
        return True

    # إذا وُجدت أخطاء spelling أو أفعال خاطئة، لا نعتبرها false positive
    critical_keywords = ["spelling", "verb", "agreement", "incorrect", "wrong", "should be"]
    for line in lines:
        if any(kw in line.lower() for kw in critical_keywords):
            return False

    # فلترة التوافه
    harmless_count = sum(
        1 for line in lines if any(re.search(pattern, line.lower()) for pattern in TRIVIAL_PATTERNS)
    )
    harmless_ratio = harmless_count / len(lines)
    return harmless_ratio >= 0.7

def should_skip_issue(issue_text):
    return any(phrase.lower() in issue_text.lower() for phrase in IGNORE_PHRASES)

def deduplicate_lines(lines):
    seen = set()
    unique = []
    for line in lines:
        if line.strip().lower() not in seen:
            seen.add(line.strip().lower())
            unique.append(line)
    return unique

# === فحص القواعد عبر GPT ===
def check_grammar(content):
    try:
        for phrase in EXCLUDED_WORDS:
            content = content.replace(phrase, "")

        prompt = (
            "Check grammar and spelling mistakes of the news item below. "
            "Only return issues that affect meaning or correctness. Ignore style, punctuation, and formatting issues. "
            "If no such issues exist, reply exactly: OK.\n\n"
            + content
        )

        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        print("🧠 Sending content to OpenAI for grammar check...", flush=True)

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a grammar checker."},
                {"role": "user", "content": prompt}
            ]
        )

        result = response.choices[0].message.content.strip()

        if is_false_positive_grammar(result):
            return "OK"

        lines = [l for l in result.splitlines() if not should_skip_issue(l)]
        lines = deduplicate_lines(lines)
        return "OK" if not lines else "\n".join(lines)

    except Exception as e:
        print(f"❌ Grammar check error: {e}", flush=True)
        return "OK"

# === إرسال البريد ===
def send_email(subject, body):
    try:
        msg = EmailMessage()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"📧 Email sent: {subject}", flush=True)
    except Exception as e:
        print(f"❌ Error sending email: {e}", flush=True)

# === المراقبة ===
def monitor_news():
    try:
        print("🔍 Checking SPA news...", flush=True)
        urls = get_latest_news_urls()

        for i, url in enumerate(urls):
            if not is_visited(url):
                print(f"📰 New article: {url}", flush=True)
                content = extract_news_content(url)
                print(f"📄 Content length: {len(content)}", flush=True)

                if content:
                    result = check_grammar(content)
                    print(f"🔎 Grammar result: {result}", flush=True)

                    issues = []
                    if result != "OK":
                        issues.append("grammar and spell")

                    subject = "✅ OK" if not issues else f"⚠️ caution, {' and '.join(issues)}"
                    body = (
                        f"Subject: {subject}\n"
                        f"News Number: #{i + 1}\n"
                        f"News Link: {url}\n"
                        f"Issue(s) Found:\n{result}"
                    )

                    send_email(subject, body)
                mark_visited(url)
    except Exception as e:
        print(f"❌ Error in monitor_news(): {e}", flush=True)

# === تشغيل المجدول ===
def run_scheduler():
    print("🟢 SPA News Monitor Service Started.", flush=True)
    init_db()
    monitor_news()
    schedule.every(5).minutes.do(monitor_news)
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    run_scheduler()
