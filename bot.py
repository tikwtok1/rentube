import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
import httpx

TOKEN = "8868474021:AAFuT8wnMxq8EdC9keC4o19uMLa2C5e3BQg"

# إعدادات متقدمة لخداع يوتيوب (Spoofing)
YDL_OPTIONS = {
    'quiet': True,
    'no_warnings': True,
    'geo_bypass': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android'],
            'api_retries': 3,
        }
    },
    'user_agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.40 Mobile Safari/537.36',
    'nocheckcertificate': True
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

async def upload_to_catbox(file_path):
    if not os.path.exists(file_path): return None
    url = "https://catbox.moe/user/api.php"
    async with httpx.AsyncClient(timeout=600.0) as client:
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

def get_video_info(url):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info, None
        except Exception as e:
            return None, str(e)

def download_media(url, quality):
    opts = YDL_OPTIONS.copy()
    if quality == 'audio':
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': '%(id)s.%(ext)s'
        })
    else:
        opts.update({
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
            'merge_output_format': 'mp4',
            'outtmpl': f'%(id)s_{quality}p.%(ext)s'
        })
        
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
        except Exception as e:
            print(f"DL Error: {e}")
            return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 البوت جاهز. أرسل رابط فيديو يوتيوب وسأجلب لك خيارات الجودة.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "youtu" not in url: return
    msg = await update.message.reply_text("🔄 جاري التحقق من الفيديو...")
    
    info, error = await asyncio.to_thread(get_video_info, url)
    if error:
        await msg.edit_text(f"❌ خطأ تقني:\n{error[:100]}")
        return

    keyboard = [
        [InlineKeyboardButton("🎥 1080p", callback_data=f"dl|1080|{url}"), InlineKeyboardButton("🎥 720p", callback_data=f"dl|720|{url}")],
        [InlineKeyboardButton("🎥 480p", callback_data=f"dl|480|{url}"), InlineKeyboardButton("🎥 360p", callback_data=f"dl|360|{url}")],
        [InlineKeyboardButton("🎵 تحميل صوت فقط", callback_data=f"dl|audio|{url}")]
    ]
    await msg.edit_text(f"📌 {info.get('title')}\nاختر الجودة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    quality, url = data[1], data[2]
    
    await query.edit_message_text("⏳ جاري التحميل... قد يستغرق الأمر بعض الوقت.")
    file_path = await asyncio.to_thread(download_media, url, quality)

    if not file_path or not os.path.exists(file_path):
        await query.edit_message_text("❌ فشل التحميل. يوتيوب لا يزال يرفض الاتصال من هذا السيرفر.")
        return

    await query.edit_message_text("📤 جاري الرفع للرابط المباشر...")
    download_url = await upload_to_catbox(file_path)

    if download_url:
        await query.edit_message_text(f"✅ تم بنجاح!\n\n🚀 الرابط المباشر:\n{download_url}")
    else:
        await query.edit_message_text("⚠️ فشل الرفع.. سأحاول إرسال الملف مباشرة.")
        try:
            if quality == 'audio': await context.bot.send_audio(query.message.chat_id, audio=open(file_path, 'rb'))
            else: await context.bot.send_video(query.message.chat_id, video=open(file_path, 'rb'))
            await query.delete_message()
        except: await query.edit_message_text("❌ حدث خطأ أثناء إرسال الملف.")
    
    if os.path.exists(file_path): os.remove(file_path)

def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()

if __name__ == '__main__':
    main()
