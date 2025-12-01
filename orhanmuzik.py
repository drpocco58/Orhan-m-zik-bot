import os
import asyncio
import logging
import requests
from fastapi import FastAPI, Request
from fastapi.responses import Response
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = "TOKENİN"
PORT = int(os.environ.get("PORT", 10000))
HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "drmuzik-bot-1.onrender.com")
WEBHOOK_URL = f"https://{HOST}/webhook"

app = FastAPI()
application = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam kral! Bot aktif.\n/sarki şarkı adı yaz, hemen gönderiyorum!")

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Şarkı adı yaz! /sarki kibariye annem")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"Aranıyor: {query}…")

    try:
        # Şarkı Evreni arama
        search_url = f"https://sarkievreni.com/?s={query.replace(' ', '+')}"
        html = requests.get(search_url).text

        # İlk mp3 linkini bul
        import re
        match = re.search(r"https://sarkievreni\.com/wp-content/uploads/[^\"]+\.mp3", html)

        if not match:
            await msg.edit_text("Şarkı bulunamadı.")
            return

        mp3_url = match.group()

        # mp3 indir
        r = requests.get(mp3_url)
        with open("song.mp3", "wb") as f:
            f.write(r.content)

        await update.message.reply_audio(open("song.mp3", "rb"), title=query, caption=query)
        await msg.delete()

    except Exception:
        await msg.edit_text("Şarkı bulunamadı.")

    finally:
        if os.path.exists("song.mp3"):
            os.remove("song.mp3")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("sarki", sarki))

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    asyncio.create_task(application.process_update(update))
    return Response(content="OK")

@app.on_event("startup")
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logging.info("Bot Webhook Açıldı!")
