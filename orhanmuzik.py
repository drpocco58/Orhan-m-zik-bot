import os
import threading
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam Orhan usta! Şarkı gönder, MP3 yapayım. 🎶")

async def download_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text

    msg = await update.message.reply_text("Arıyorum usta... 🔍")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            entry = info["entries"][0]
            url = entry["webpage_url"]
            title = entry.get("title", "Bilinmeyen Şarkı")

            await msg.edit_text(f"İndiriyorum usta… 🎵\n{title}")
            ydl.download([url])

            filename = ydl.prepare_filename(entry).rsplit(".", 1)[0] + ".mp3"

            with open(filename, "rb") as audio:
                await update.message.reply_audio(audio, title=title)

            os.remove(filename)
            await msg.delete()

    except Exception as e:
        await msg.edit_text(f"Hata: {str(e)}")

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_song))
    app.run_polling()

# BOTU THREAD İLE BAŞLAT
threading.Thread(target=run_bot).start()
