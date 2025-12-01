import os
import logging
import yt_dlp
import glob
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# BURAYA KENDİ BOT TOKENINI YAZ
TOKEN = "BURAYA_TOKENINI_YAZ"

# 2025'te sorunsuz çalışan ayarlar
YDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'outtmpl': '/tmp/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'geo_bypass': True,
    'nocheckcertificate': True,
    'retries': 20,
    'fragment_retries': 20,
    'extractor_retries': 10,
    'skip_unavailable_fragments': True,
    'default_search': 'ytsearch5:',
    'cookiefile': '/app/cookies.txt' if os.path.exists('/app/cookies.txt') else None,
    'extractor_args': {
        'youtube': {
            'skip': ['hls', 'dash'],
            'player_client': ['android', 'web', 'ios'],
        }
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam kral! Bot aktif ✅\n"
        "Şarkı adı yaz, hemen gönderiyorum!\n"
        "Örnek: Müslüm Gürses Unutamadım"
    )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if query.lower().startswith('/sarki '):
        query = query[7:].strip()

    if len(query) < 2:
        await update.message.reply_text("Şarkı adı yazman lazım kral 😅")
        return

    status_msg = await update.message.reply_text(f"🔍 Aranıyor: {query}")

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            search = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if not search or not search.get('entries'):
                await status_msg.edit_text("❌ Şarkı bulunamadı, farklı isimle dene.")
                return

            entry = None
            for e in search['entries']:
                if e and e.get('duration', 0) <= 1200:
                    entry = e
                    break
            if not entry:
                entry = search['entries'][0]

            title = entry['title']
            await status_msg.edit_text(f"⬇️ İndiriliyor:\n{title}")

            ydl.download([entry['url']])

            # Dosyayı bul (bazen başlıkta özel karakter oluyor)
            files = glob.glob("/tmp/*.mp3")
            if not files:
                await status_msg.edit_text("❌ Ses dosyası oluşturulamadı.")
                return
            filename = files[0]

            if os.path.getsize(filename) > 50 * 1024 * 1024:
                await status_msg.edit_text("❌ Dosya çok büyük (50MB+), gönderilemedi.")
                os.remove(filename)
                return

            with open(filename, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=title,
                    caption=f"🎵 {title}\n\nKeyfini çıkar kral ❤️"
                )

            await status_msg.delete()
            os.remove(filename)

    except Exception as e:
        logging.error(f"Hata: {e}")
        await status_msg.edit_text("❌ Bir şeyler ters gitti, tekrar dene kral.")

# Handler'lar
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))
app.add_handler(CommandHandler("sarki", download_and_send))

# Railway webhook
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"https://{os.environ['RAILWAY_STATIC_URL']}/{TOKEN}"
    )
