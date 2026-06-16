import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
import httpx

TOKEN = "8868474021:AAFuT8wnMxq8EdC9keC4o19uMLa2C5e3BQg"

# سيرفر إبقاء البوت حياً في Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# دالة رفع الملفات للحصول على رابط مباشر
async def upload_to_catbox(file_path):
    if not os.path.exists(file_path): return None
    url = "https://catbox.moe/user/api.php"
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': f}
                data = {'reqtype': 'fileupload'}
                response = await client.post(url, data=data, files=files)
                if response.status_code == 200 and "https://" in response.text:
                    return response.text.strip()
        except Exception as e:
            print(f"Upload error: {e}")
    return None

# دالة جلب معلومات الفيديو والجودات المتاحة
def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info, None
        except Exception as e:
            return None, str(e)

# دالة التحميل بناءً على اختيار المستخدم
def download_media(video_id, quality):
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'outtmpl': f'%(id)s_%(resolution)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}}
    }

    if quality == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['outtmpl'] = f'%(id)s_audio.%(ext)s'
    else:
        # دمج الفيديو والصوت للجودة المطلوبة
        ydl_opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            # تصحيح الامتدادات بعد التحميل للـ FFmpeg
            file_path = ydl.prepare_filename(info)
            if quality == 'audio':
                file_path = file_path.rsplit('.', 1)[0] + '.mp3'
            return file_path
        except Exception as e:
            print(f"DL Error: {e}")
            return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 مرحباً بك! أرسل الآن رابط **فيديو يوتيوب واحد** وسأعطيك خيارات الجودة لتحميله أو تحويله لمقطع صوتي.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "youtu" not in url:
        await update.message.reply_text("⚠️ الرجاء إرسال رابط يوتيوب صحيح لمقطع فيديو.")
        return

    msg = await update.message.reply_text("🔄 جاري فحص الفيديو...")
    
    loop = asyncio.get_event_loop()
    info, error = await loop.run_in_executor(None, get_video_info, url)

    if error or not info:
        await msg.edit_text(f"❌ تعذر جلب معلومات الفيديو. إذا استمر هذا الخطأ فهذا يعني أن سيرفر Render محظور حالياً من يوتيوب.\nالخطأ التقني: {error[:100]}")
        return

    video_id = info.get('id')
    title = info.get('title', 'فيديو يوتيوب')

    # لوحة المفاتيح التفاعلية (الأزرار)
    keyboard = [
        [
            InlineKeyboardButton("🎥 1080p", callback_data=f"dl|1080|{video_id}"),
            InlineKeyboardButton("🎥 720p", callback_data=f"dl|720|{video_id}")
        ],
        [
            InlineKeyboardButton("🎥 480p", callback_data=f"dl|480|{video_id}"),
            InlineKeyboardButton("🎥 360p", callback_data=f"dl|360|{video_id}")
        ],
        [
            InlineKeyboardButton("🎵 تحميل كصوت (MP3) فقط", callback_data=f"dl|audio|{video_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.edit_text(f"📌 **{title}**\n\nاختر الجودة المطلوبة للتحميل:", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('|')
    if len(data) != 3 or data[0] != 'dl':
        return
    
    quality = data[1]
    video_id = data[2]

    quality_text = "صوت (MP3)" if quality == 'audio' else f"فيديو بدقة {quality}p"
    await query.edit_message_text(f"⏳ جاري تحميل [{quality_text}]... الرجاء الانتظار.")

    loop = asyncio.get_event_loop()
    file_path = await loop.run_in_executor(None, download_media, video_id, quality)

    if not file_path or not os.path.exists(file_path):
        await query.edit_message_text("❌ فشل التحميل من يوتيوب. قد يكون الفيديو محمياً.")
        return

    await query.edit_message_text("📤 تم التحميل بنجاح! جاري توليد الرابط المباشر...")
    
    download_url = await upload_to_catbox(file_path)

    if download_url:
        await query.edit_message_text(f"✅ **اكتملت العملية!**\n\n🎯 الجودة: {quality_text}\n📥 **رابط التحميل المباشر:**\n{download_url}")
    else:
        # الإرسال الاحتياطي مباشرة على تليجرام إذا فشل الرابط المباشر
        await query.edit_message_text("⚠️ فشل توليد الرابط المباشر للملف.. جاري إرسال الملف لك مباشرة هنا في تليجرام كبديل.")
        try:
            if quality == 'audio':
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=open(file_path, 'rb'))
            await query.edit_message_text("✅ تم إرسال الملف بنجاح.")
        except Exception as e:
            await query.edit_message_text("❌ فشل الإرسال المباشر أيضاً (قد يكون حجم الملف أكبر من الحد المسموح به في تليجرام وهو 50MB للبوتات).")
    
    # حذف الملف من السيرفر لتفريغ المساحة
    try:
        os.remove(file_path)
    except:
        pass


def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()

