import os
import yt_dlp
from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext import ApplicationBuilder

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Render'da ekleyeceksin

app = FastAPI()


ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
    "cookiefile": "cookies.txt"
}

telegram_app = ApplicationBuilder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! Şarkı adı ya da YouTube linki gönder, MP3 olarak atayım. 🎶"
    )


async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("Arıyorum kral... 🔍")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)

            if not info or "entries" not in info or not info["entries"]:
                await msg.edit_text("Şarkı bulunamadı kral.")
                return

            entry = info["entries"][0]
            title = entry.get("title", "Bilinmeyen Şarkı")
            url = entry["webpage_url"]

            if entry.get("duration", 0) > 600:
                await msg.edit_text("Bu şarkı 10 dakikadan uzun kral, indiremiyorum.")
                return

            await msg.edit_text(f"İndiriyorum… 🎵\n{title}")

            ydl.download([url])

            filename = ydl.prepare_filename(entry).rsplit(".", 1)[0] + ".mp3"

            if not os.path.exists(filename):
                await msg.edit_text("Dönüştürme hatası oldu kral.")
                return

            await msg.edit_text("Gönderiyorum… 🚀")

            with open(filename, "rb") as audio:
                await context.bot.send_audio(
                    chat_id=chat_id, audio=audio, title=title, timeout=120
                )

            os.remove(filename)
            await msg.delete()

    except Exception as e:
        await msg.edit_text(f"Hata: {str(e)}")


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))


@app.post("/webhook")
async def telegram_webhook(update: dict):
    update_obj = Update.de_json(update, telegram_app.bot)
    await telegram_app.process_update(update_obj)
    return "ok"


@app.on_event("startup")
async def startup():
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
