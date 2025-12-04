import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot token'ı Render ortam değişkeninden alıyoruz
TOKEN = os.getenv("BOT_TOKEN")

# yt-dlp ayarları
ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
    "cookiefile": "cookies.txt"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! Şarkı adı ya da YouTube linki gönder, MP3 olarak atayım. 🎶"
    )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("Arıyorum kral... 🔍")

    try:
        # Arama
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)

            if not info or "entries" not in info or not info["entries"]:
                await msg.edit_text("Şarkı bulunamadı kral, başka bir şey dene.")
                return

            entry = info["entries"][0]
            title = entry.get("title", "Bilinmeyen Şarkı")
            url = entry["webpage_url"]

            # 10 dakikadan uzun ise gönderme
            if entry.get("duration", 0) > 600:
                await msg.edit_text("Bu şarkı 10 dakikadan uzun kral, indiremiyorum.")
                return

            await msg.edit_text(f"İndiriyorum kral… 🎵\n{title}")

            # Video indirme
            ydl.download([url])

            # mp3 dosya adını bulma
            filename = ydl.prepare_filename(entry).rsplit(".", 1)[0] + ".mp3"

            if not os.path.exists(filename):
                await msg.edit_text("Dönüştürme hatası oluştu kral.")
                return

            await msg.edit_text("Gönderiyorum… 🚀")

            # Dosyayı gönder
            with open(filename, "rb") as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    title=title,
                    timeout=120
                )

            os.remove(filename)
            await msg.delete()

    except Exception as e:
        await msg.edit_text(f"Hata oldu kral: {str(e)}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot polling modunda başladı…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
