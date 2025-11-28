import logging
import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor

# Telegram Bot Library Imports
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# Web Framework Imports
from flask import Flask, request

# Download Tool
import yt_dlp

# Set up logging
# Botun çalışması sırasında hata ayıklama için log seviyesi INFO olarak ayarlandı.
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Ortam Değişkenleri ---
# BOT_TOKEN ve WEB_SERVICE_URL, Render ortam değişkenlerinden alınır.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_SERVICE_URL = os.environ.get("WEB_SERVICE_URL")

# --- Flask Uygulaması ---
# Flask, Render üzerinde bir web sunucusu olarak çalışır ve Telegram güncellemelerini alır.
app = Flask(__name__)

# Thread Pool for background song processing
# Şarkı indirme ve yükleme işlemlerini Flask uygulamasını engellemeden arka planda yapmak için kullanılır.
executor = ThreadPoolExecutor(max_workers=5)

# --- Bot İşlevleri ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Başlangıç mesajını gönderir."""
    await update.message.reply_text('Merhaba! Ben Dr Müzik Botu.\nBana "/sarki Sanatçı - Şarkı Adı" formatında bir mesaj gönderin, ben de size şarkıyı göndereyim.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yardım mesajını gönderir."""
    await update.message.reply_text('Kullanım:\n/sarki <Şarkı Adı> - Aradığınız şarkıyı indirir ve size gönderir.')

async def handle_song_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gelen mesajı kontrol eder ve şarkı işleme görevini başlatır."""
    if not update.message.text.startswith('/sarki '):
        return

    # '/sarki ' kısmını mesajdan ayırır.
    query = update.message.text[len('/sarki '):].strip()
    
    if not query:
        await update.message.reply_text("Lütfen bir şarkı adı girin. Örn: /sarki Tarkan - Kuzu Kuzu")
        return

    logger.info(f"Yeni şarkı isteği alındı: {query} (Kullanıcı ID: {update.effective_user.id})")
    await update.message.reply_text(f'"{query}" aranıyor ve indiriliyor. Bu işlem birkaç saniye sürebilir, lütfen bekleyin...')

    # İndirme ve gönderme işlemini arka plan thread'ine gönderir.
    # Flask uygulamasının kilitlenmemesi için bu gereklidir.
    executor.submit(
        lambda: threading.Thread(
            target=process_song_in_thread,
            args=(query, update.effective_chat.id, context.application)
        ).start()
    )


def process_song_in_thread(query: str, chat_id: int, application: Application):
    """Arka planda çalışan indirme ve gönderme işlevi."""
    temp_filename = f"music_file_{chat_id}.mp3" 
    
    try:
        # 1. Şarkıyı Bulma ve İndirme
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': temp_filename, # Geçici dosya adını kullan
            'noplaylist': True,
            'max_downloads': 1,
            'default_search': 'ytsearch',
            'quiet': True,
            'extract_flat': 'in_playlist',
        }

        info = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Arama yap ve ilk sonucu indir
                info = ydl.extract_info(query, download=True)
                if 'entries' in info:
                    info = info['entries'][0]

            except yt_dlp.utils.DownloadError as e:
                logger.error(f"İndirme hatası: {e}")
                application.create_task(
                    application.bot.send_message(
                        chat_id,
                        f'Üzgünüm, "{query}" ile ilgili bir sonuç bulunamadı veya indirme hatası oluştu.'
                    )
                )
                return

        # 2. Şarkıyı Telegram'a Gönderme
        if info and os.path.exists(temp_filename):
            title = info.get('title', 'Bilinmeyen Başlık')
            artist = info.get('artist') or info.get('creator') or 'Bilinmeyen Sanatçı'
            duration = info.get('duration')
            
            caption = f"🎶 {title}\n🎤 {artist}"
            
            with open(temp_filename, 'rb') as audio_file:
                # Telegram'a dosyayı gönder (async işlem, create_task kullanıyoruz)
                application.create_task(
                    application.bot.send_audio(
                        chat_id=chat_id, 
                        audio=audio_file, 
                        caption=caption,
                        title=title,
                        performer=artist,
                        duration=duration
                    )
                )
            logger.info(f"Şarkı başarıyla gönderildi: {title}")

        else:
             application.create_task(
                application.bot.send_message(
                    chat_id,
                    f'Üzgünüm, "{query}" için dosya bulunamadı.'
                )
            )

    except Exception as e:
        logger.error(f"Genel hata oluştu: {e}", exc_info=True)
        application.create_task(
            application.bot.send_message(
                chat_id,
                f'İşlem sırasında beklenmeyen bir hata oluştu: {str(e)}'
            )
        )
    finally:
        # 3. Geçici Dosyayı Silme
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception as e:
                logger.error(f"Dosya silme hatası: {e}")


# --- Ana Uygulama Kurulumu ve Çalıştırma ---

# Application'ı global olarak oluştur
application = Application.builder().token(BOT_TOKEN).build()

# Handler'ları Application'a ekle
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\s*/sarki\s+'), handle_song_request))


@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook():
    """Telegram'dan gelen güncellemeleri işler."""
    try:
        # Gelen JSON verisini al
        data = request.json
        if data:
            # Gelen JSON verisini Telegram Update nesnesine dönüştür
            update = Update.de_json(data, application.bot)
            
            # Güncellemeyi Application'a gönder (asenkron görev olarak)
            await application.process_update(update)
            
        return "OK"
    except Exception as e:
        logger.error(f"Webhook işleme hatası: {e}")
        return "ERROR", 500

@app.route('/', methods=['GET'])
def index():
    """Sağlık kontrolü için ana sayfa."""
    return "Dr Müzik Botu Çalışıyor!"

def setup_webhook_and_start_flask():
    """Webhook'u ayarlar ve Flask'ı başlatır."""
    if not BOT_TOKEN or not WEB_SERVICE_URL:
        logger.error("HATA: BOT_TOKEN veya WEB_SERVICE_URL ayarlanmamış. Uygulama başlatılamıyor.")
        return 1

    # 1. Telegram Webhook'u Ayarla (Sadece bir kere çağrılmalı)
    webhook_url = WEB_SERVICE_URL + "/" + BOT_TOKEN
    
    # 2. Webhook'u kaydetmek için istek gönder
    set_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(set_webhook_url, timeout=5)
        response.raise_for_status() 
        result = response.json()
        if result['ok']:
            logger.info(f"Telegram Webhook başarıyla ayarlandı: {webhook_url}")
        else:
            logger.error(f"Telegram Webhook ayarlanırken hata: {result.get('description', 'Bilinmeyen Hata')}")
            return 1 # Hata durumunda uygulama başlamasın
    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook kaydı sırasında bağlantı hatası: {e}")
        return 1
        
    # 3. Flask uygulamasını başlat (Render'ın dinleyeceği portta)
    port = int(os.environ.get("PORT", "5000"))
    logger.info(f"Flask sunucusu 0.0.0.0:{port} adresinde başlatılıyor...")
    app.run(host='0.0.0.0', port=port)
    
    return 0

if __name__ == '__main__':
    # Flask uygulamasını başlatma fonksiyonunu çağır
    setup_webhook_and_start_flask()
