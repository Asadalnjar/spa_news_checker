# استخدم صورة Python الرسمية كأساس
FROM python:3.10-slim

# تثبيت أدوات النظام الأساسية والاعتماديات اللازمة لـ Chrome وSelenium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libu2f-udev \
    libvulkan1 \
    xdg-utils \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# تثبيت Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# تعيين متغير بيئة لتجنب أخطاء الكروم
ENV CHROME_BIN=/usr/bin/google-chrome
ENV PATH="${PATH}:/usr/bin"

# تثبيت Selenium وباقي المكتبات
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# نسخ ملفات المشروع
COPY . /app
WORKDIR /app

# الأمر الذي يتم تنفيذه عند بدء الحاوية
CMD ["python", "main.py"]
