import os
import time
import requests
import sqlite3
import openai
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler

# إعداد متغيرات البيئة
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO   = os.environ.get(" EMAIL_TO")

# التحقق من وجود المتغيراتs
if not all([OPENAI_API_KEY, EMAIL_USER, EMAIL_PASS, EMAIL_TO]):
    raise EnvironmentError("❌ تأكد من تعيين جميع المتغيرات البيئية: OPENAI_API_KEY, EMAIL_USER, EMAIL_PASS, EMAIL_TO")

# إعداد مفتاح OpenAI
openai.api_key = OPENAI_API_KEY

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# التحقق من الرابط الجديد
def is_new_url(url):
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute('SELECT url FROM visited WHERE url = ?', (url,))
    result = c.fetchone()
    if result is None:
        c.execute('INSERT INTO visited (url) VALUES (?)', (url,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# جلب روابط الأخبار من الموقع
def fetch_news_links():
    base_url = "https://www.spa.gov.sa/en/news/latest-news"
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('a', class_='news-item__link')
    links = ['https://www.spa.gov.sa' + a['href'] for a in articles if a.get('href')]
    return links

# جلب محتوى الخبر
def fetch_news_content(news_url):
    try:
        response = requests.get(news_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = '\n'.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
        return full_text
    except Exception as e:
        print(f"[ERROR] Failed to fetch content: {e}")
        return None

# التدقيق اللغوي باستخدام ChatGPT
def grammar_check(text):
    try:
        prompt = (
            "Check grammar and spelling mistakes of the news item below. "
            "If there are no mistakes, reply: OK. If there are mistakes, reply: Caution, and list all found mistakes.\n\n"
            f"{text}"
        )
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"[ERROR] OpenAI API failed: {e}")
        return "ERROR: Failed to analyze text."

# إرسال البريد الإلكتروني
def send_email(subject, body):
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_TO

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"[INFO] Email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

# المهمة الأساسية التي تعمل كل 20 دقيقة
def run_job():
    print(f"[DEBUG] run_job() triggered at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    links = fetch_news_links()
    for link in links:
        if is_new_url(link):
            print(f"[NEW] Processing: {link}")
            text = fetch_news_content(link)
            if text:
                result = grammar_check(text)
                subject = "News Check: OK" if "OK" in result else "News Check: Caution"
                email_body = f"News URL: {link}\n\nResult:\n{result}"
                send_email(subject, email_body)
        else:
            print(f"[SKIP] Already processed: {link}")

# تشغيل المجدول
if __name__ == "__main__":
    print("[DEBUG] Starting spa_news_checker script...")
    init_db()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_job, 'interval', minutes=20)
    print("[INFO] Scheduler started. Checking every 20 minutes...")

    run_job()  # تشغيل أول مرة مباشرة

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[INFO] Scheduler stopped.")
