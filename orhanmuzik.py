import os
import asyncio
import nest_asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI  # Health check için (requirements'a ekleyeceğiz)
from fastapi.responses import JSONResponse
import uvicorn

# nest_asyncio'yu uygula
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'drmuzik-bot-1.onrender.com')}/webhook"

# FastAPI app for health check (Render probe'u için)
fast_app = FastAPI()

@fast_app.get("/health")
async def health_check():
    return JSONResponse(status_code=200, content={"status": "healthy"})

# Telegram bot app (ayrı)
telegram_app = Application.builder().token(TOKEN).build()

# yt-dlp ayarları (aynı)
ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "outtmpl": "song.%(ext)s",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "noplaylist": True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! 🎉\n\nŞarkı indirmek için:\n/sarki leyla ile mecnun\n/sarki despacito\n\nHemen dene!"
    )

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Şarkı adını yaz kral! Örnek: /sarki emrah belalim")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Aranıyor: {query}\nBiraz bekle Orhan usta buluyor...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
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
                    caption=f"🎧 {title}\n\nBaşka şarkı? /sarki [isim]"
                )
            await msg.delete()
        else:
            await msg.edit_text("Şarkı bulunamadı kardeşim 😢\nTekrar dene veya farklı isim yaz.")

    except Exception as e:
        logger.error(f"Hata: {e}")
        await msg.edit_text("Bir hata oldu, tekrar dene... 😞\nÖrnek: /sarki emrah belalim")

    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

# Telegram handler'ları ekle
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("sarki", sarki))

async def main():
    # Webhook ayarla
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook set edildi: {WEBHOOK_URL}")

    # FastAPI'yi Telegram webhook ile entegre et (PTB docs'a göre)
    from telegram.ext import WebhookServer
    server = WebhookServer(listen="0.0.0.0", port=PORT, url_path="/webhook", webhook_url=WEBHOOK_URL)
    server.app.add_api_route("/health", health_check, methods=["GET"])  # Health ekle
    server.app.include_router(fast_app)  # FastAPI'yi dahil et

    print("Bot çalışıyor ve güncellemeleri bekliyor...")
    await telegram_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL,
        webhook_server=server
    )

if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
