import os
import asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"

# yt-dlp ayarları
ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "outtmpl": "song.%(ext)s",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "noplaylist": True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral!\n\nŞarkı indirmek için:\n/sarki leyla ile mecnun\n/sarki despacito"
    )

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Şarkı adını yaz kral! /sarki şeker oğlan")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"Aranıyor: {query}\nBiraz bekle...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            title = info.get("title", "Bilinmeyen Şarkı")

        filename = "song.mp3"
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            if os.path.getsize(filename) > 50 * 1024 * 1024:
                await update.message.reply_voice(open(filename, "rb"), caption=title)
            else:
                await update.message.reply_audio(open(filename, "rb"), title=title, caption=title)
            await msg.delete()
        else:
            await msg.edit_text("Şarkı bulunamadı kardeşim")

    except Exception as e:
        logger.error(f"Hata: {e}")
        await msg.edit_text("Bir hata oldu, tekrar dene")

    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

async def main():
    app = Application.builder().token(TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sarki", sarki))

    # Webhook ayarla (ilk seferde)
    await app.bot.set_webhook(url=WEBHOOK_URL)

    # BOTU BAŞLAT (TEK SATIR, EN ÖNEMLİ KISIM!)
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    asyncio.run(main())
