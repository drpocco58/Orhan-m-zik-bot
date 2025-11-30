import os
import asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
RENDER_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"

ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "outtmpl": "song.%(ext)s",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "noplaylist": True,
    "default_search": "ytsearch1:",
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! 🎉\n\nSarki indirmek icin:\n/sarki leyla ile mecnun\n/sarki despacito"
    )

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Sarki adini yaz kral! Ornek: /sarki leyla ile mecnun")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"Araniyor: {query}\nBiraz bekle...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            title = info.get("title", "Bilinmeyen Sarki")
            filename = "song.mp3"

        if not os.path.exists(filename):
            await msg.edit_text("Sarki bulunamadi.")
            return

        filesize = os.path.getsize(filename)
        if filesize > 50 * 1024 * 1024:
            await msg.edit_text("Dosya buyuk, sesli mesaj olarak gonderiyorum...")
            await update.message.reply_voice(open(filename, "rb"), caption=title)
        else:
            await update.message.reply_audio(
                open(filename, "rb"),
                title=title,
                performer="Orhan Muzik Bot",
                caption=title
            )
        await msg.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("Hata oldu, tekrar dene.")

    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

async def main():
    # Webhook kontrol
    app_temp = ApplicationBuilder().token(TOKEN).build()
    webhook_url = f"{RENDER_URL}/webhook"
    info = await app_temp.bot.get_webhook_info()
    if info.url != webhook_url:
        await app_temp.bot.set_webhook(url=webhook_url)
        print(f"Webhook set: {webhook_url}")
    else:
        print(f"Webhook already set: {webhook_url}")

    # Ana bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sarki", sarki))

    print("Bot is running...")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    asyncio.run(main())
