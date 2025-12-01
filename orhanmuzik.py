import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import shutil

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")

# ffmpeg'i otomatik kur (Railway'de ilk çalıştırmada kuruyor)
if not shutil.which("ffmpeg"):
    os.system("apt update && apt install -y ffmpeg")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam! Şarkı adı yaz, hemen indireyim 🎧")

async def muzik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("Bir şarkı adı yaz")
        return

    status_msg = await update.message.reply_text("Arıyorum...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': '/usr/bin/ffmpeg',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            entries = info.get('entries', [info])
            filename = ydl.prepare_filename(entries[0]).rsplit('.', 1)[0] + '.mp3'

        await status_msg.edit_text("Gönderiliyor...")
        with open(filename, 'rb') as f:
            await update.message.reply_audio(f, caption=entries[0]['title'], title=entries[0]['title'])

        os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text("Şarkı bulunamadı veya hata oldu, başka dene.")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, muzik))
application.run_polling(allowed_updates=Update.ALL_TYPES)
