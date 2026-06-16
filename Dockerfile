FROM ubuntu:22.04

# منع الأسئلة التفاعلية أثناء التثبيت
ENV DEBIAN_FRONTEND=noninteractive

# تثبيت التحديثات والاعتمادات الأساسية (بايثون، ffmpeg، nodejs، وأدوات التحميل)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    nodejs \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# تحميل النسخة الرسمية المبنية مسبقاً من Telegram Bot API لأجهزة الـ x86_64
# (نقوم بوضعه في المسار /usr/local/bin ليعمل كأمر مباشر في النظام)
RUN wget -O /usr/local/bin/telegram-bot-api https://github.com/tdlib/telegram-bot-api/releases/latest/download/telegram-bot-api-linux-amd64 \
    && chmod +x /usr/local/bin/telegram-bot-api

WORKDIR /app

# نسخ ملف المتطلبات وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# نسخ كود البوت
COPY bot.py .

# أمر التشغيل المزدوج (السيرفر المحلي في الخلفية + البوت)
CMD telegram-bot-api --local --api-id=25571618 --api-hash=0fb4c207a9ee083e9df259fa87309536 & python3 bot.py
