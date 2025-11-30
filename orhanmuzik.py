import os
import asyncio
import nest_asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
HOST = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'drmuzik-bot-1.onrender.com')}"

# FastAPI ile health check + webhook aynı anda
app = FastAPI()

@app.get("/health")          # ← Render buraya bakacak
async def health():
    return {"status": "ok"}

@app.post("/webhook")        # ← Telegram buraya POST atacak
async def telegram_webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, bot)
    await dp.process_update(update)
    return JSONResponse(content={"ok": True})

# Telegram bot kısmı
bot = Application.builder().token(TOKEN).build()

ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "outtmpl": "song.%(ext)s",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "noplaylist": True,
    "http_headers": {"User-Agent": "Mozilla/5.0"}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam kral! 🎉\n/sarki [şarkı adı] yaz, hemen indiriyorum!")

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Şarkı adı yaz! /sarki emrah belalım")
        return
    query = " ".join(context.args)
    msg = await update.message.reply_text("🔍 Aranıyor...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            title = info.get("title", "Bilinmeyen")
        if os.path.exists("song.mp3"):
            await update.message.reply_audio(open("song.mp3", "rb"), title=title, caption=title)
            await msg.delete()
    except Exception as e:
        await msg.edit_text("Hata oldu, tekrar dene.")
    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("sarki", sarki))
dp = bot

# FastAPI'yi çalıştır
import uvicorn
if __name__ == "__main__":
    # Webhook set et
    asyncio.run(bot.bot.set_webhook(url=f"{HOST}/webhook"))
    print("Bot çalışıyor, health check aktif!")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
