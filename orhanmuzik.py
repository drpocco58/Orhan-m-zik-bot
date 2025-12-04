import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot token'ı Render ortam değişkeninden alıyoruz
TOKEN = os.getenv("BOT_TOKEN")

# yt-dlp ayarları (cookies.txt ile age-restricted da çalışır)
ydl_opts = {
    "format": "bestaudio",
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
        "Selam kral! YouTube linki ya da şarkı adı yaz, MP3 olarak atayım.\n"
        "Age-restricted videolar da dahil her şey çalışır! 🎶"
    )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("Aranıyor... 🔍")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if not info or 'entries' not in info or not info['entries']:
                await msg.edit_text("Bulunamadı kral, başka dene.")
                return

            entry = info['entries'][0]
            title = entry.get('title', 'Bilinmeyen Şarkı')
            duration = entry.get('duration', 0)
            if duration and duration > 600:  # 10 dakikadan uzun olmasın
                await msg.edit_text("Video 10 dakikadan uzun, atamıyorum kral.")
                return

            await msg.edit_text(f"İndiriliyor...\n🎵 {title}")
            ydl.download([entry['webpage_url']])

            filename = ydl.prepare_filename(entry).rsplit('.', 1)[0] + '.mp3'
            if not os.path.exists(filename):
                await msg.edit_text("Dönüştürme hatası oldu, başka şarkı dene.")
                return

            await msg.edit_text("Gönderiliyor... 🚀")
            with open(filename, 'rb') as audio:
                await context.bot.send_audio(chat_id=chat_id, audio=audio, title=title, timeout=120)

            await msg.delete()
            os.remove(filename)

    except Exception as e:
        await msg.edit_text(f"Bir hata oldu kral: {str(e)}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot polling modunda başladı...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
