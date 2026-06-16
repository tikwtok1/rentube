# استخدام حاوية سيرفر تليجرام المحلي الجاهزة والمبنية رسمياً
FROM aiogram/telegram-bot-api:latest

# تثبيت البايثون، الفايرفوكس المساعد للدمج (FFmpeg) و Node.js لتخطي قيود يوتيوب
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    nodejs \
    bash

WORKDIR /app

# نسخ ملف الاعتمادات وتثبيت مكتبات البايثون داخل النظام
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# نسخ ملف البوت الخاص بك
COPY bot.py .

# فتح المنافذ الافتراضية داخل الحاوية
EXPOSE 8081 8080

# أمر التشغيل الثنائي: تشغيل سيرفر تليجرام المحلي، ثم تشغيل كود البوت فوراً
CMD telegram-bot-api --local --api-id=25571618 --api-hash=0fb4c207a9ee083e9df259fa87309536 & python3 bot.py
