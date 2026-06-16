# استخدام حاوية سيرفر تليجرام المحلي الجاهزة والمبنية رسمياً
FROM aiogram/telegram-bot-api:latest

# تثبيت البايثون، والـ FFmpeg المساعد للدمج و Node.js لتخطي قيود يوتيوب
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    nodejs \
    bash

# إجبار الحاوية على قراءة معرفات التطبيق كمتغيرات بيئة إجبارية قبل التشغيل
ENV TELEGRAM_API_ID=25571618
ENV TELEGRAM_API_HASH=0fb4c207a9ee083e9df259fa87309536
ENV TELEGRAM_LOCAL_MODE=true

WORKDIR /app

# نسخ ملف الاعتمادات وتثبيت مكتبات البايثون داخل النظام
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# نسخ ملف البوت الخاص بك
COPY bot.py .

# فتح المنافذ الافتراضية داخل الحاوية
EXPOSE 8081 8080

# أمر التشغيل النهائي المستقر
CMD ["sh", "-c", "telegram-bot-api & python3 bot.py"]
