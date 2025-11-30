import os
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8304604344:AAGJg949AqR7iitfqWGkvdu8QFtDe7rIScc"
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

async def sarki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kardeşim şarkı adını yazmadın.")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"Arıyorum Orhan usta, bekle... 🎧\n\n{query}")

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "outtmpl": "song.mp3",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch:{query}"])

    await update.message.reply_audio(open("song.mp3", "rb"))

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("sarki", sarki))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()
