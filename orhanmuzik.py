import os
import asyncio
import nest_asyncio  # Event loop çakışmasını önler
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# nest_asyncio'yu uygula (Render'da loop sorununu çözer)
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'drmuzik-bot-1.onrender.com')}/webhook"

# yt-dlp ayarları (aynı kaldı)
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

    # Webhook ayarla
    await app.bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook set edildi: {WEBHOOK_URL}")

    # Botu başlat (nest_asyncio sayesinde loop çakışmaz)
    print("Bot çalışıyor ve güncellemeleri bekliyor...")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    # Event loop'u doğru yönet (Render için)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
