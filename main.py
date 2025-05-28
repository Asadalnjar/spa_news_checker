import os
import time
import requests
import sqlite3
import openai
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler
from twilio.rest import Client

# إعداد المتغيرات من البيئة
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
WHATSAPP_TO = os.environ.get("WHATSAPP_TO")  # مثال: whatsapp:+9665xxxxxxxx

# تحقق من المتغيرات الأساسية
if not all([OPENAI_API_KEY, TWILIO_SID, TWILIO_TOKEN, WHATSAPP_TO]):
    raise EnvironmentError("❌ تأكد من تعيين جميع المتغيرات البيئية: OPENAI_API_KEY, TWILIO_SID, TWILIO_TOKEN, WHATSAPP_TO")

# إعداد مفتاح OpenAI
openai.api_key = OPENAI_API_KEY

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)")
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

# جلب روابط الأخبار من موقع SPA
def fetch_news_links():
    try:
        base_url = "https://www.spa.gov.sa/en/news/latest-news"
        response = requests.get(base_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('a', class_='news-item__link')
        links = ['https://www.spa.gov.sa' + a['href'] for a in articles if a.get('href')]
        return links
    except Exception as e:
        print(f"[ERROR] Failed to fetch news links: {e}")
        return []

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

# إرسال رسالة WhatsApp
def send_whatsapp(body):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            body=body,
            from_='whatsapp:+14155238886',  # رقم Sandbox في Twilio
            to=WHATSAPP_TO
        )
        print(f"[INFO] WhatsApp message sent. SID: {message.sid}")
    except Exception as e:
        print(f"[ERROR] Failed to send WhatsApp message: {e}")

# المهمة الأساسية
def run_job():
    print(f"[DEBUG] run_job() triggered at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    links = fetch_news_links()
    if not links:
        print("[INFO] No news links found.")
    for link in links:
        if is_new_url(link):
            print(f"[NEW] Processing: {link}")
            text = fetch_news_content(link)
            if text:
                result = grammar_check(text)
                subject = "✅ OK" if "OK" in result else "⚠️ Caution"
                message_body = f"{subject}\n{link}\n\n{result}"
                send_whatsapp(message_body)
        else:
            print(f"[SKIP] Already processed: {link}")

# بدء التشغيل
if __name__ == "__main__":
    print("[DEBUG] Starting spa_news_checker script...")
    init_db()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_job, 'interval', minutes=20)
    print("[INFO] Scheduler started. Checking every 20 minutes...")
    run_job()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[INFO] Scheduler stopped.")
