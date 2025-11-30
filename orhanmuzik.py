import os
import asyncio
import nest_asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Event loop fix for Render
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'drmuzik-bot-1.onrender.com')}/webhook"

# yt-dlp ayarları (Render anti-bot için ekstra)
ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "outtmpl": "song.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "noplaylist": True,
    "extract_flat": False,
    "cookiefile": None,  # Cookie yok
    "extractor_retries": 3,
    "fragment_retries": 3,
    "sleep_interval": 1,  # Rate limit önle
    "max_sleep_interval": 5,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    "geo_bypass": True,
    "source_address": "0.0.0.0",  # Render IP'sini gizle
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! 🎉\n\nŞarkı indirmek için:\n/sarki emrah belalim\n/sarki hadise prenses\n\nHemen dene, Orhan usta hazır!"
    )

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Şarkı adını yaz kral! Örnek: /sarki emrah belalim")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Aranıyor: {query}\nBiraz bekle, indiriliyor...")

    try:
        # Arama + indirme
        search_query = f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if not info:
                await msg.edit_text("Şarkı bulunamadı kardeşim 😢\nFarklı isim dene!")
                return
            title = info.get("title", "Bilinmeyen Şarkı")

        filename = "song.mp3"
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            filesize = os.path.getsize(filename)
            if filesize > 50 * 1024 * 1024:  # 50MB üstü voice
                await update.message.reply_voice(open(filename, "rb"), caption=f"🎵 {title}")
            else:
                await update.message.reply_audio(
                    open(filename, "rb"),
                    title=title,
                    performer="Orhan Müzik Bot",
                    caption=f"🎧 {title}\n\nBaşka? /sarki [isim]"
                )
            await msg.delete()
        else:
            await msg.edit_text("İndirilemedi, YouTube sorunlu olabilir. Tekrar dene!")

    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp DownloadError: {e}")
        await msg.edit_text("YouTube indirme hatası (bot algılandı). Farklı şarkı dene veya bekle!")
    except Exception as e:
        logger.error(f"Genel hata: {e}")
        await msg.edit_text("Bir hata oldu, tekrar dene... 😞")

    finally:
        # Dosya temizle
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

# Non-command mesajlar için (eğer /sarki yazmazsa)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Komut kullan kral! /start veya /sarki [şarkı adı]")

async def main():
    app = Application.builder().token(TOKEN).build()

    # Handler'lar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sarki", sarki))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Webhook set et (sadece bir kez)
    webhook_info = await app.bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    else:
        logger.info(f"Webhook zaten set: {WEBHOOK_URL}")

    logger.info("Bot çalışıyor, mesajları bekliyor...")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
