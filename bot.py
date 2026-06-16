import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# توكن البوت الخاص بك
TOKEN = "8868474021:AAFuT8wnMxq8EdC9keC4o19uMLa2C5e3BQg"

# نظام التأكد من عمل السيرفر (مطلوب لـ Render)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot and Local API are working!")

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
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    video_entries = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(fixed_url, download=False)
            if not info_dict:
                return None, "تعذر استخراج بيانات الرابط."
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

def download_single_video(video_id, quality_choice):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    if quality_choice == "low":
        format_opt = "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst"
    elif quality_choice == "medium":
        format_opt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best"
    else: # high
        format_opt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"

    ydl_opts = {
        'format': format_opt,
        'outtmpl': f'%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                if os.path.exists(f"{base}.mp4"):
                    filename = f"{base}.mp4"
            return filename
        except Exception as e:
            return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك! البوت يعمل الآن على Render بنظام السيرفر المحلي المدمج لدعم حتى 2 جيجابايت لكل فيديو.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "youtube.com" not in url and not url.startswith('@'):
        await update.message.reply_text("⚠️ من فضلك أرسل رابط قناة صحيح.")
        return
    context.user_data['current_channel_url'] = url
    keyboard = [
        [InlineKeyboardButton("📁 جودة ضعيفة", callback_data="low")],
        [InlineKeyboardButton("🎬 جودة متوسطة (480p)", callback_data="medium")],
        [InlineKeyboardButton("🚀 أعلى جودة متوفرة (حتى 2GB)", callback_data="high")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ اختر الجودة المطلوبة:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality_choice = query.data
    url = context.user_data.get('current_channel_url')

    if not url:
        await query.edit_message_text("⚠️ انتهت الجلسة.")
        return

    quality_text = {"low": "ضعيفة", "medium": "متوسطة", "high": "العالية"}[quality_choice]
    await query.edit_message_text(f"🔄 تم اختيار الجودة **{quality_text}**.\nجاري جلب الفيديوهات...")

    loop = asyncio.get_event_loop()
    video_entries, channel_name = await loop.run_in_executor(None, get_channel_videos_list, url)

    if video_entries is None or not video_entries:
        await query.message.reply_text("❌ تعذر جلب الفيديوهات.")
        return

    total_videos = len(video_entries)
    await query.message.reply_text(f"📊 **القناة:** {channel_name}\n🎥 **العدد:** {total_videos}\n⏳ بدأ السحب التلقائي (دعم حتى 2GB)...")

    for idx, entry in enumerate(video_entries, start=1):
        video_id = entry['id']
        video_title = entry['title']
        progress_msg = await query.message.reply_text(f"📥 تحميل {idx}/{total_videos}:\n**{video_title}**")
        
        file_path = await loop.run_in_executor(None, download_single_video, video_id, quality_choice)
        
        if file_path and os.path.exists(file_path):
            await progress_msg.edit_text(f"📤 رفع {idx}/{total_videos} (عبر السيرفر المحلي)...")
            try:
                with open(file_path, 'rb') as video_file:
                    await query.message.reply_video(
                        video=video_file,
                        caption=f"🎥 #{idx} من {total_videos}\nعنوان: {video_title}"
                    )
                await progress_msg.delete()
            except Exception as send_error:
                await progress_msg.edit_text(f"⚠️ فشل إرسال الفيديو رقم {idx}: {str(send_error)}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
        else:
            await progress_msg.edit_text(f"❌ تعذر تحميل الفيديو رقم {idx}")

        if idx % 10 == 0 and idx < total_videos:
            await asyncio.sleep(10)

    await query.message.reply_text(f"✨ اكتملت العملية لقناة **{channel_name}**.")

def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # ربط السكريبت بالسيرفر المحلي الذي سيعمل داخل نفس الحاوية على منفذ 8081
    application = (
        Application.builder()
        .token(TOKEN)
        .base_url("http://127.0.0.1:8081/bot")
        .local_mode(True)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling()

if __name__ == '__main__':
    main()

