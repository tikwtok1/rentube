import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import httpx

TOKEN = "8868474021:AAFuT8wnMxq8EdC9keC4o19uMLa2C5e3BQg"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online and working smoothly!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def fix_channel_url(url):
    url = url.strip()
    if url.startswith('@'):
        return f"https://www.youtube.com/{url}/videos"
    if "youtube.com" in url and not url.endswith("/videos") and not url.endswith("/shorts"):
        if url.endswith("/"):
            url = url[:-1]
        return f"{url}/videos"
    return url

def get_channel_videos_list(channel_url):
    fixed_url = fix_channel_url(channel_url)
    ydl_opts = {'extract_flat': True, 'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
    video_entries = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(fixed_url, download=False)
            if not info_dict: return None, "تعذر استخراج البيانات."
            channel_title = info_dict.get('title', 'قناة يوتيوب')
            if 'entries' in info_dict:
                for entry in info_dict['entries']:
                    if entry:
                        v_id = entry.get('id')
                        v_title = entry.get('title')
                        if v_id and v_title and len(v_id) <= 12:
                            video_entries.append({'id': v_id, 'title': v_title})
            return video_entries, channel_title
        except Exception as e:
            return None, str(e)

def download_single_video(video_id):
    # الحل الجذري: روابط يوتيوب رسمية + تخطي حظر السيرفرات السحابية
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # تحميل أفضل جودة مدمجة مباشرة لتخفيف الضغط على سيرفر Render المجاني
        'outtmpl': f'%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            return ydl.prepare_filename(info)
        except Exception as e:
            print(f"Error downloading {video_id}: {e}")
            return None

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
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 البوت جاهز. أرسل رابط قناة يوتيوب للبدء.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    await update.message.reply_text("🔄 جاري جلب الفيديوهات...")
    loop = asyncio.get_event_loop()
    video_entries, channel_name = await loop.run_in_executor(None, get_channel_videos_list, url)

    if not video_entries:
        await update.message.reply_text("❌ تعذر جلب الفيديوهات. تأكد من صحة الرابط.")
        return

    total_videos = len(video_entries)
    await update.message.reply_text(f"📊 القناة: {channel_name}\n🎥 العدد: {total_videos}\n⏳ بدأ السحب والرفع...")

    for idx, entry in enumerate(video_entries, start=1):
        video_id = entry['id']
        video_title = entry['title']
        progress_msg = await update.message.reply_text(f"📥 جاري معالجة {idx}/{total_videos}:\n**{video_title}**")
        
        file_path = await loop.run_in_executor(None, download_single_video, video_id)
        
        if file_path and os.path.exists(file_path):
            await progress_msg.edit_text(f"📤 تم التحميل.. جاري توليد الرابط المباشر...")
            download_url = await upload_to_catbox(file_path)
            
            if download_url:
                await update.message.reply_text(
                    f"🎬 **فيديو رقم {idx} من {total_videos}**\n\n"
                    f"📌 **العنوان:** {video_title}\n"
                    f"🚀 **الرابط المباشر:**\n{download_url}"
                )
                await progress_msg.delete()
            else:
                await progress_msg.edit_text(f"⚠️ فشل الرفع للفيديو رقم {idx}. قد يكون حجمه تجاوز 200MB.")
            
            os.remove(file_path)
        else:
            await progress_msg.edit_text(f"❌ تعذر تحميل الفيديو رقم {idx} من يوتيوب.")

def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
