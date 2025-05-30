import requests
from bs4 import BeautifulSoup
import openai
import smtplib
from email.message import EmailMessage
import sqlite3
import schedule
import time
import os

# 🧠 استيراد Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

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

# === تهيئة قاعدة البيانات ===
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
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.binary_location = "/usr/bin/google-chrome"

        driver = webdriver.Chrome(options=chrome_options)


        driver.get(SPA_URL)
        time.sleep(5)

        elements = driver.find_elements(By.CSS_SELECTOR, "div.card-body a.text-dark")
        urls = [
            "https://www.spa.gov.sa" + elem.get_attribute("href")
            for elem in elements if "/en/news/" in elem.get_attribute("href")
        ]

        driver.quit()
        print(f"✅ [Selenium] Found {len(urls)} news URLs", flush=True)
        return urls
    except Exception as e:
        print(f"❌ Selenium error: {e}", flush=True)
        return []

# === استخراج محتوى الخبر ===
def extract_news_content(url):
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        body = soup.select_one("div.article-text")
        return body.get_text(separator="\n").strip() if body else ""
    except Exception as e:
        print(f"❌ Error extracting news from {url}: {e}", flush=True)
        return ""

# === التحقق من الأخطاء اللغوية عبر ChatGPT ===
def check_grammar(content):
    try:
        prompt = (
            "Check grammar and spelling mistakes of the news item below. "
            "If there are no mistakes, reply: OK. "
            "If there are any mistakes, reply: Caution, and list all found mistakes.\n\n"
            + content
        )
        print("🧠 Sending content to OpenAI for grammar check...", flush=True)
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error during grammar check: {e}", flush=True)
        return "Error during grammar check"

# === إرسال البريد الإلكتروني ===
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

# === تنفيذ المهمة ===
def monitor_news():
    try:
        print("🔍 Checking SPA news...", flush=True)
        urls = get_latest_news_urls()
        for i, url in enumerate(urls):
            if not is_visited(url):
                print(f"📰 New article: {url}", flush=True)
                content = extract_news_content(url)
                if content:
                    result = check_grammar(content)
                    status = "OK" if result == "OK" else "Caution"
                    body = f"News #{i+1}\n{url}\nStatus: {status}"
                    if status == "Caution":
                        body += f"\nMistakes:\n{result}"
                    send_email(f"[SPA News Check] News #{i+1} - {status}", body)
                mark_visited(url)
    except Exception as e:
        print(f"❌ Error in monitor_news(): {e}", flush=True)

# === الجدولة والتشغيل ===
def run_scheduler():
    print("🟢 SPA News Monitor Service Started.", flush=True)
    init_db()
    monitor_news()  # تشغيل مباشر عند البدء
    schedule.every(1).hours.do(monitor_news)
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    run_scheduler()
