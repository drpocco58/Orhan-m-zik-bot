import os
import asyncio
import tempfile
import shutil
import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

# YouTube indirici ayarları
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
}

def download_song(query: str):
    tmpdir = tempfile.mkdtemp()
    outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

    opts = dict(YDL_OPTS)
    opts["outtmpl"] = outtmpl

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=True)

    entry = info["entries"][0]
    for f in os.listdir(tmpdir):
        if f.endswith(".mp3"):
            return os.path.join(tmpdir, f), entry.get("title")

    return None, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hoş geldin Orhan usta! Şarkı adını yaz.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    msg = await update.message.reply_text("🔍 Arıyorum...")

    loop = asyncio.get_running_loop()
    try:
        mp3_path, title = await loop.run_in_executor(None, download_song, query)

        if not mp3_path:
            await msg.edit_text("Şarkıyı bulamadım kardeşim.")
            return

        await msg.edit_text("Gönderiyorum...")

        with open(mp3_path, "rb") as f:
            await update.message.reply_audio(audio=f, title=title)

        await msg.delete()

    finally:
        try:
            shutil.rmtree(os.path.dirname(mp3_path), ignore_errors=True)
        except:
            pass


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN environment variable eksik!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot başladı (polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
