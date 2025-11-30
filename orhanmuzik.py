import os
import asyncio
import logging
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import Response
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 10000))
HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "drmuzik-bot-1.onrender.com")
WEBHOOK_URL = f"https://{HOST}/webhook"

app = FastAPI()

# BOT OLUŞTUR
application = ApplicationBuilder().token(TOKEN).build()

# KOMUTLAR
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam kral! Bot aktif\n/sarki şarkı adı yaz, hemen gönderiyorum!")

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Şarkı adı yaz! /sarki kibariye annem")
        return
    query = " ".join(context.args)
    msg = await update.message.reply_text(f"Aranıyor: {query}…")
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "outtmpl": "song.%(ext)s",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            title = info.get("title", "Şarkı")
        await update.message.reply_audio(open("song.mp3", "rb"), title=title, caption=title)
        await msg.delete()
    except Exception as e:
        await msg.edit_text("Şarkı bulunamadı.")
    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("sarki", sarki))

# HEALTH CHECK
@app.get("/health")
async def health():
    return {"status": "ok"}

# WEBHOOK
@app.post("/webhook")
async def webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)
    asyncio.create_task(application.process_update(update))
    return Response(content="OK")

# BAŞLAT
@app.on_event("startup")
async def on_startup():
    await application.initialize()  # BU SATIR EKSİKTİ!
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logging.info("Bot başladı ve webhook aktif!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
