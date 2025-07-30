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
# 🧠 Selenium Imports
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


EXCLUDED_WORDS = [
    # الأشهر الميلادية
    "January", "February", "March", "April", "May", "June", 
    "July", "August", "September", "October", "November", "December",
    # الأشهر الهجرية
    "Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Awwal",
    "Jumada al-Thani", "Rajab", "Sha'ban", "Ramadan", "Shawwal",
    "Dhu al-Qi'dah", "Dhu al-Hijjah",
    # أيام الأسبوع
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    # معلومات الوكالة
    "The Saudi Press Agency (SPA), established in 1971, is a prime reference for those interested in local news and events. The agency provides accurate and real-time media content in several languages. It operates ​​according to professional best practices and makes use of the latest effective communication techniques. SPA seeks to be an influential voice of the Kingdom of Saudi Arabia in the Arab and Islamic worlds, as well as globally.",
    "Agency services", "Tenders", "Contact", "Privacy policy", 
    "Terms-and-Conditions", "Public services", "Private Sector Feedback Platform", 
    "Public Consultation Platform"
]

# ✅ Table A: Official Names and Titles
TABLE_A_NAMES = [
    "Custodian of the Two Holy Mosques King Salman bin Abdulaziz Al Saud",
    "His Royal Highness Prince Mohammed bin Salman bin Abdulaziz Al Saud, Crown Prince and Prime Minister",
    "Minister of Foreign Affairs Prince Faisal bin Farhan bin Abdullah",
    "Minister of Interior Prince Abdulaziz bin Saud bin Naif bin Abdulaziz",
    "Minister of Defense Prince Khalid bin Salman bin Abdulaziz",
    "Minister of National Guard Prince Abdullah bin Bandar bin Abdulaziz",
    "Minister of Energy Prince Abdulaziz bin Salman bin Abdulaziz",
    "Minister of Sport Prince Abdulaziz bin Turki bin Faisal",
    "Minister of Culture Prince Bader bin Abdullah bin Farhan",
    "Minister of State for Foreign Affairs, Cabinet Member, and Climate Envoy Adel Al-Jubeir",
    "Minister of Media Salman Al-Dossary",
    "Minister of Investment Khalid Al-Falih",
    "Minister of Commerce Majid Al-Kassabi",
    "Minister of Human Resources and Social Development Ahmed Al-Rajhi",
    "Minister of Transport and Logistic Services Saleh Al-Jasser",
    "Minister of Justice Walid Al-Samaani",
    "Minister of Finance Mohammed Aljadaan",
    "Minister of Industry and Mineral Resources Bandar Alkhorayef",
    "Minister of Economy and Planning Faisal Alibrahim",
    "Minister of Environment, Water and Agriculture Abdulrahman Alfadley",
    "Minister of Communications and Information Technology Abdullah Alswaha",
    "Minister of Municipalities and Housing Majed Al-Hogail",
    "Minister of Health Fahad AlJalajel",
    "Minister of Education Yousef Al-Benyan",
    "Minister of Tourism Ahmed Al-Khateeb",
    "Minister of Hajj and Umrah Tawfig Al-Rabiah",
    "Minister of Islamic Affairs, Dawah and Guidance Sheikh Dr. Abdullatif Al Alsheikh",
    "Vice Minister of Foreign Affairs Waleed Elkhereiji"
]

# ✅ Table B: Regions and Common Mistakes
TABLE_B_NAMES = {
    "Riyadh": ["Riyadh city", "Riyadh City"],
    "Makkah": ["Mecca", "Makkah city"],
    "Madinah": ["Medina", "Madinah city"],
    "Qassim": ["Qassim city", "Al-Qassim"],
    "Eastern Region": ["Eastern Province", "Eastern region"],
    "Aseer Region": ["Asir Region", "Aseer region"],
    "Jazan": ["Jazan city", "Jazan City", "Jazan Region"],
    "Najran": ["Najran city", "Najran Region"],
    "Al-Baha": ["Al Baha", "Al-Baha city"],
    "Tabuk": ["Tabouk", "Tabuk Region"],
    "Hail": ["Hail city", "Hail Region"],
    "Al-Jouf": ["Al Jouf", "Al-Jouf Region"],
    "Northern Borders": ["Northern Borders Region", "Northern Province", "Northern Border"]
}

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
        chrome_options.binary_location = "/usr/bin/chromium"
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/112 Safari/537.36")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(SPA_URL)
        time.sleep(7)  # منح وقت كافٍ لتحميل الصفحة بالكامل

        # ✅ التقاط روابط الأخبار الحقيقية التي تبدأ بـ /en/N
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='/en/N']")
        urls = []

        for elem in elements:
            href = elem.get_attribute("href")
            if href:
                full_url = href if href.startswith("http") else "https://www.spa.gov.sa" + href
                urls.append(full_url)

        # حفظ الصفحة للمراجعة إذا لزم الأمر
        with open("spa_page_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

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
        chrome_options.add_argument("--remote-debugging-port=9223")
        chrome_options.binary_location = "/usr/bin/chromium"
        chrome_options.add_argument("user-agent=Mozilla/5.0")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # قائمة احتمالات أماكن النص
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
        # نحاول كل Selector حتى نجد النص
        for selector in possible_selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                article = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue

        # إذا لم نجد أي عنصر من القائمة، نعمل Fallback على كل <p>
        if not article:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                )
                article = driver  # سنأخذ الفقرات من كل الصفحة
                print(f"⚠️ Using fallback to scrape all <p> tags for {url}")
            except:
                print(f"⚠️ No article container or <p> tags found for {url}")
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                driver.quit()
                return ""

        # جمع الفقرات
        if article == driver:  # fallback mode
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
        else:
            paragraphs = article.find_elements(By.TAG_NAME, "p")

        # تنظيف النصوص: استبعاد الفقرات القصيرة والمكررة
        seen = set()
        content_lines = []
        for p in paragraphs:
            text = p.text.strip()
            if len(text.split()) < 4:  # تجاهل الفقرات القصيرة جدًا
                continue
            if text and text not in seen:
                seen.add(text)
                content_lines.append(text)

        content = "\n".join(content_lines)
        driver.quit()

        if not content.strip():
            print(f"⚠️ No content extracted from: {url}", flush=True)

        return content

    except Exception as e:
        print(f"❌ Selenium error while extracting content: {e}", flush=True)
        return ""



# === التحقق من الأخطاء اللغوية عبر ChatGPT ===
# === فلترة التنبيهات غير المهمة في القواعد ===
def is_false_positive_grammar(result):
    """
    تعود True إذا كانت كل أو أغلب الملاحظات تافهة ولا تستحق التنبيه.
    """
    ignore_keywords = [
        # مشاكل الترجمة أو التنسيق غير المؤثرة
        "capitalized", "capitalize", "comma", "period", "punctuation", "space", "spacing",
        "hyphen", "dash", "format", "date", "duplicate", "redundancy", "unclear",
        "terms-and-conditions", "voice reader", "r101",
        # العبارات الشائعة من GPT
        "a space is needed", "extra space", "could use punctuation",
        "should have proper quotation marks", "should be revised for clarity",
        "add a comma", "remove the extra asterisk", "separate it from",
        "comma after", "congruent with", "corrected to a standard format"
    ]

    lines = [line for line in result.splitlines() if line.strip()]
    if not lines:
        return True

    # حساب نسبة الملاحظات التافهة
    harmless_count = sum(1 for line in lines if any(kw in line.lower() for kw in ignore_keywords))
    harmless_ratio = harmless_count / len(lines)

    # إذا كل أو أغلب الملاحظات تافهة → نعتبرها False Positive
    return harmless_ratio >= 0.7


def check_grammar(content):
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        # حذف العبارات المتكررة من النص قبل الإرسال إلى GPT
        for phrase in EXCLUDED_WORDS:
            content = content.replace(phrase, "")

        excluded_text = "\n".join(EXCLUDED_WORDS)

        # إعداد الـ Prompt
        prompt = (
            "Check grammar and spelling mistakes of the news item below. "
            "If there are no mistakes, reply: OK. "
            "If there are any mistakes, reply: Caution, and list all found mistakes.\n\n"
            "Do NOT check or modify the following words or phrases even if they seem wrong:\n"
            f"{excluded_text}\n\n"
            + content
        )

        print("🧠 Sending content to OpenAI for grammar check...", flush=True)

        # طلب التصحيح من GPT
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a grammar checker."},
                {"role": "user", "content": prompt}
            ]
        )

        # النتيجة الأولية من GPT
        result = response.choices[0].message.content.strip()

        # إذا النتيجة False Positive → ترجع OK
        if is_false_positive_grammar(result):
            return "OK"

        # فلترة الملاحظات بعد الرد من GPT
        ignore_keywords = [
            "capitalized", "capitalize", "comma", "period", "punctuation", "space", "spacing",
            "hyphen", "dash", "format", "date", "duplicate", "redundancy", "unclear",
            "terms-and-conditions", "voice reader", "r101"
        ]
        filtered_issues = []
        for line in result.splitlines():
            if not any(kw in line.lower() for kw in ignore_keywords):
                filtered_issues.append(line)

        # إذا لا يوجد ملاحظات مهمة بعد الفلترة → OK
        result = "\n".join(filtered_issues).strip() if filtered_issues else "OK"

        return result

    except openai.error.RateLimitError:
        print("❌ Rate limit exceeded – please check your OpenAI usage quota.", flush=True)
        return "Error during grammar check: Rate limit exceeded"

    except openai.error.AuthenticationError:
        print("❌ Authentication failed – please verify your OpenAI API key.", flush=True)
        return "Error during grammar check: Authentication failed"

    except openai.error.OpenAIError as e:
        print(f"❌ OpenAI API error: {e}", flush=True)
        return f"Error during grammar check: {str(e)}"

    except Exception as e:
        print(f"❌ Unknown error during grammar check: {e}", flush=True)
        return f"Error during grammar check: {str(e)}"

# دالة التحقق من الأخطاء في Table A
def check_table_a_violations(content):
    violations = []
    for official in TABLE_A_NAMES:
        # تحقق من وجود الاسم بالضبط (حساس لحالة الأحرف)
        if official not in content:
            # لو كان موجود بصيغة خاطئة (مثلاً بدون أحرف كبيرة)
            for line in content.splitlines():
                if official.lower() in line.lower():
                    violations.append(f"- Incorrect form or casing: Expected '{official}'")
                    break
    return violations
#دالة فحص Table B
def check_table_b_violations(content):
    violations = []
    for correct_name, incorrect_variants in TABLE_B_NAMES.items():
        for wrong in incorrect_variants:
            if wrong in content:
                violations.append(f"- Incorrect: '{wrong}' → Correct: '{correct_name}'")
    return violations


# دالة فحص قواعد Table C
def check_table_c_rules(content):
    violations = []
    lines = content.splitlines()

    # ✅ Rule 1: لا تضع نقطة في نهاية العنوان
    if lines:
        headline = lines[0].strip()
        if headline.endswith("."):
            violations.append("Rule 1 Violation: Headline ends with a period '.'")

    # ✅ Rule 2: استخدم زمن المضارع في العنوان
    # مثال: avoid "started" → use "starts"
    headline_lower = lines[0].lower() if lines else ""
    if "started" in headline_lower or "concluded" in headline_lower:
        violations.append("Rule 2 Violation: Headline uses past tense instead of present")

    # ✅ Rule 3: علامات اقتباس مزدوجة غير مقبولة
    if '"' in content:
        violations.append("Rule 3 Violation: Use single quotes (‘ ’) instead of double quotes (“ ”)")

    # ✅ Rule 4: Subject-Verb Agreement
    if re.search(r"\bMinister[s]?, [A-Z][a-z]+ [A-Z][a-z]+ discuss(es)? cooperation\b", content):
        violations.append("Rule 4 Violation: Subject-verb agreement issue (use 'discuss' with plural)")

    # ✅ Rule 5: استخدام prepositions الخاطئة
    if "at Riyadh" in content:
        violations.append("Rule 5 Violation: Use 'in Riyadh' instead of 'at Riyadh'")

    # ✅ Rule 6: Spelling common mistakes
    if "meat in Cairo" in content or "sing MoU" in content:
        violations.append("Rule 6 Violation: Likely typo - check 'meat' or 'sing'")

    # ✅ Rule 7: علامات ترقيم (مثل وجود مسافة قبل الفاصلة)
    if re.search(r"\s+,", content) or re.search(r"\.\.", content):
        violations.append("Rule 7 Violation: Improper punctuation spacing or repeated dots")

    # ✅ Rule 8: استخدام "The Minister" بحروف كبيرة في السياق
    if re.search(r"\bThe Minister\b", content):
        violations.append("Rule 8 Violation: Use lowercase 'the minister' in running text")

    return violations


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
                print(f"📄 Content length: {len(content)}", flush=True)

                if content:
                    # 1. Grammar & Spelling Check
                    result = check_grammar(content)
                    print(f"🔎 Grammar result: {result}", flush=True)

                    # 2. Table A: Official Names Check
                    table_a_issues = check_table_a_violations(content)

                    # 3. Table B: Region Names Check
                    table_b_issues = check_table_b_violations(content)

                    # 4. Table C: Writing Rules Check
                    table_c_issues = check_table_c_rules(content)

                    # 5. Collect all issue types
                    issues = []
                    if result.strip() != "OK" and not is_false_positive_grammar(result):
                        issues.append("grammar and spell")
                    if table_a_issues:
                        issues.append("Table A")
                    if table_b_issues:
                        issues.append("Table B")
                    if table_c_issues:
                        issues.append("Table C")

                    subject = "✅ OK" if not issues else f"⚠️ caution, {' and '.join(issues)}"

                    # 6. Compose email body
                    if subject == "OK":
                        body = (
                            f"Subject: OK\n"
                            f"News Number: #{i + 1}\n"
                            f"News Link: {url}\n"
                            f"Status: No major issues found."
                        )
                    else:
                        body = (
                            f"Subject: {subject}\n"
                            f"News Number: #{i + 1}\n"
                            f"News Link: {url}\n"
                            f"Issue(s) Found:\n"
                        )

                        if result != "OK":
                            body += "\nGrammar/Spelling:\n"
                            body += result if isinstance(result, str) else "\n".join(result)

                        if table_a_issues:
                            body += "\n\nTable A (Titles/Names):\n"
                            body += "\n".join(table_a_issues)

                        if table_b_issues:
                            body += "\n\nTable B (Regions/Cities):\n"
                            body += "\n".join(table_b_issues)

                        if table_c_issues:
                            body += "\n\nTable C (Writing Rules):\n"
                            body += "\n".join(table_c_issues)

                    # 7. Send email
                    send_email(subject, body)
                    print(f"📧 Email sent: {subject}", flush=True)

                else:
                    print("⚠️ No content extracted.", flush=True)

                mark_visited(url)

    except Exception as e:
        print(f"❌ Error in monitor_news(): {e}", flush=True)

# === الجدولة والتشغيل ===
def run_scheduler():
    print("🟢 SPA News Monitor Service Started.", flush=True)
    init_db()
    monitor_news()  # تشغيل مباشر عند البدء
    schedule.every(5).minutes.do(monitor_news)
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    run_scheduler()
