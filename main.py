import requests
from bs4 import BeautifulSoup
import openai
import smtplib
from email.message import EmailMessage
import sqlite3
import schedule
import time
import os

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
        res = requests.get(SPA_URL)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = soup.select('a.text-decoration-none')
        urls = ["https://www.spa.gov.sa" + a["href"] for a in articles if "/en/news/" in a["href"]]
        return urls
    except Exception as e:
        print(f"Error fetching news URLs: {e}")
        return []

# === استخراج محتوى الخبر ===
def extract_news_content(url):
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        body = soup.select_one("div.article-text")
        return body.get_text(separator="\n").strip() if body else ""
    except Exception as e:
        print(f"Error extracting news: {e}")
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error during grammar check: {e}"

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
    except Exception as e:
        print(f"Error sending email: {e}")

# === تنفيذ المهمة ===
def monitor_news():
    print("🔍 Checking news updates...")
    urls = get_latest_news_urls()
    for i, url in enumerate(urls):
        if not is_visited(url):
            content = extract_news_content(url)
            if content:
                result = check_grammar(content)
                status = "OK" if result == "OK" else "Caution"
                email_body = f"News #{i+1}\n{url}\nStatus: {status}"
                if status == "Caution":
                    email_body += f"\nMistakes:\n{result}"
                send_email(f"[SPA News Check] News #{i+1} - {status}", email_body)
            mark_visited(url)

# === الجدولة كل ساعة ===
def run_scheduler():
    init_db()
    schedule.every(1).hours.do(monitor_news)
    print("✅ News monitor running every 1 hour...")
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    run_scheduler()
