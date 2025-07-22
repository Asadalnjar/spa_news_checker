# 1. صورة Python الرسمية
FROM python:3.10-slim

# 2. تثبيت أدوات النظام الأساسية
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libu2f-udev \
    libvulkan1 \
    xdg-utils \
    fonts-liberation \
    ca-certificates \
    chromium \
    chromium-driver \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 3. تعيين متغيرات البيئة
ENV CHROME_BIN=/usr/bin/chromium
ENV PATH="/usr/local/bin:$PATH"

# 4. نسخ الاعتماديات وتثبيتها
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 5. نسخ المشروع
COPY . /app
WORKDIR /app

# 6. تشغيل التطبيق
CMD ["bash", "start.sh"]
