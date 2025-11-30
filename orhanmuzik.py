import os
import asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.constants import ParseMode
from telegram.error import TimedOut, NetworkError

# Log ayarları (Render loglarında güzel gözüksün diye)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# TOKEN'INI BURAYA YAZ (güvenlik için .env kullanmak daha iyi ama şimdilik böyle)
TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"  # <-- BURAYI DEĞİŞTİRME, ZATEN SENİN

# Render ortam değişkenleri
PORT = int(os.environ.get("PORT", 10000))  # Render varsayılan 10000 kullanıyor
RENDER_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"  # Önemli!

# yt-dlp ayarları (daha stabil)
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
    "default_search": "ytsearch1:",
}

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kardeşim şarkı adını yaz be! Örnek: /sarki leyla ile mecnun")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 <b>Aranıyor:</b> {query}\n\nBiraz bekle Orhan usta buluyor...", parse_mode=ParseMode.HTML)

    try:
        # İndir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            title = info.get("title", "Bilinmeyen Şarkı")
            filename = "song.mp3"

        # Dosya var mı kontrol et
        if not os.path.exists(filename):
            await msg.edit_text("Şarkı bulunamadı veya indirilemedi 😢")
            return

        filesize = os.path.getsize(filename)
        
        # Telegram 50MB sınırı var, büyükse sesli mesaj olarak gönder
        if filesize > 50 * 1024 * 1024:  # 50MB'den büyükse
            await msg.edit_text("Dosya büyük, sesli mesaj olarak gönderiyorum 🎤")
            await update.message.reply_voice(open(filename, "rb"), caption=f"🎵 {title}")
        else:
            await update.message.reply_audio(
                open(filename, "rb"),
                title=title,
                performer="Orhan Müzik Bot",
                caption=f"🎧 <b>{title}</b>\n\nBotu @orhannnmuzik ile kullanabilirsin",
                parse_mode=ParseMode.HTML
            )

        await msg.delete()

    except Exception as e:
        logger.error(f"Hata: {e}")
        await msg.edit_text("Bir hata oldu kardeşim, tekrar dene... 😞")

    finally:
        # İndirilen dosyayı sil (disk dolmasın)
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! 🎉\n\n"
        "Şarkı indirmek için:\n"
        "<code>/sarki leyla ile mecnun</code>\n"
        "<code>/sarki despacito</code>\n\n"
        "Hemen dene!",
        parse_mode=ParseMode.HTML
    )

def main() -> None:
    app: Application = ApplicationBuilder().token(TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sarki", sarki))

    # Webhook'u ayarla (ilk çalıştırmada otomatik kurar)
    webhook_url = f"{RENDER_URL}/webhook"
    print(f"Bot başlatılıyor... Webhook URL: {webhook_url}")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    temp_app = ApplicationBuilder()...
    main()
