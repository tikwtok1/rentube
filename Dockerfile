FROM alpine:3.19

# تثبيت جميع الاعتمادات والنظام المساعد للدمج والسيرفر المدمج
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    nodejs \
    telegram-bot-api \
    bash

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY bot.py .

# أمر التشغيل المزدوج: تشغيل سيرفر تليجرام في الخلفية، ثم تشغيل كود البوت
CMD telegram-bot-api --local --api-id=25571618 --api-hash=0fb4c207a9ee083e9df259fa87309536 & python3 bot.py
