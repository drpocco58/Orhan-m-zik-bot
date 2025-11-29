import os
import logging
import asyncio
import tempfile
import yt_dlp
import telegram
from flask import Flask, request, jsonify
from telegram.ext import Application, CommandHandler
from werkzeug.wrappers import Response
import threading
import time

# =================================================================
# 1. YAPILANDIRMA VE LOGLAMA
# =================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ortam değişkenlerini al
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL") 
DOWNLOAD_TIMEOUT_SECONDS = 90 # İndirme ve yükleme için maksimum bekleme süresini 90 saniyeye çıkardık (Render sınırlarına karşı ekstra önlem)

# Webhook yolları
WEBHOOK_PATH = f'/{BOT_TOKEN}' 
WEBHOOK_URL = WEB_SERVICE_URL + WEBHOOK_PATH

# Flask uygulamasını başlat
app = Flask(__name__)

# Global bot uygulama nesnesi ve kurulum durumu
application: Application = None
BOT_SETUP_DONE = False

# =================================================================
# 2. BOT KOMUTLARI
# =================================================================

async def start_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışır."""
    try:
        await update.message.reply_text(
            "Merhaba! Ben Orhan Müzik Botu. İstediğiniz müziği Youtube'dan indirip size gönderebilirim.\n\n"
            "Kullanım: /sarki [Şarkı Adı] [Sanatçı Adı]\n\n"
            "Örnek: /sarki Tarkan Kuzu Kuzu"
        )
    except Exception as e:
        logger.error(f"/start komutu işlenirken hata: {e}")

def _send_audio_sync(chat_id, downloaded_file, video_info):
    """
    Bu fonksiyon ayrı bir thread (iş parçacığı) içinde SENKRON olarak çalışır.
    Uzun süren dosya yüklemelerinin ana asenkron döngüyü bozmasını engeller.
    """
    if not application:
        logger.error("Uygulama nesnesi (application) başlatılmadı. Ses gönderilemiyor.")
        return

    try:
        # Telegram Bot nesnesini alıyoruz
        bot = application.bot
        
        # Yükleme işleminin zaman aşımını kontrol eder
        bot.set_default_request(timeout=DOWNLOAD_TIMEOUT_SECONDS) 

        with open(downloaded_file, 'rb') as audio_file:
            # Senkronize bot metotlarını kullanarak 'Event loop closed' hatasını önleriz.
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=video_info.get('title', 'Bilinmeyen Şarkı'),
                performer=video_info.get('artist', video_info.get('channel', 'Bilinmeyen Sanatçı')),
                caption="Müziğiniz hazır! Bizi kullandığınız için teşekkürler."
            )
        logger.info(f"✅ Şarkı başarıyla gönderildi: {video_info.get('title', 'Bilinmeyen')}")

    except Exception as e:
        logger.error(f"❌ Senkronize gönderme sırasında kritik hata: {e}")
        error_message = f"❌ Şarkıyı gönderirken bir hata oluştu. Lütfen tekrar deneyin."
        try:
            # Hata mesajını göndermeyi deneriz
            bot.send_message(chat_id=chat_id, text=error_message)
        except Exception as msg_e:
             logger.error(f"Hata mesajı gönderme başarısız oldu: {msg_e}")

    finally:
        # Temizleme
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            logger.info(f"Geçici dosya silindi: {downloaded_file}")

async def search_and_send_music(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """Kullanıcının isteğini alır, YouTube'da arar ve indirmeyi başlatır."""
    
    if not context.args:
        await update.message.reply_text("Lütfen bir şarkı adı ve sanatçı belirtin.\nÖrnek: /sarki Tarkan Kuzu Kuzu")
        return

    query = " ".join(context.args)
    initial_message = None # Başlangıç mesajını daha sonra kullanmak için None olarak tanımlıyoruz
    
    try:
        # Hızlı yanıt vererek Render'ın zaman aşımı süresini uzatırız
        initial_message = await update.message.reply_text(f"'{query}' için arama yapılıyor ve indirme başlatılıyor. Lütfen bekleyin...")
        logger.info(f"Yeni istek: {query}")
        
        temp_dir = tempfile.gettempdir()
        downloaded_file = None
        video_info = None

        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'extract_flat': 'in_playlist',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(temp_dir, 'music_%(id)s.%(ext)s'), 
            'limit_rate': '1M', 
            'logger': logger,
            'no_warnings': True,
            'geo_bypass': True,
            'ffmpeg_location': 'ffmpeg', 
        }
        
        # 1. YouTube'dan bilgiyi al ve indir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.params['logger'] = logger 
            # Timeout'u indirme/bilgi alma aşamasına ekleyerek kilitlenmeyi engelleriz.
            info = ydl.extract_info(f"ytsearch1:{query}", download=False, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            
            if 'entries' not in info or not info['entries']:
                await initial_message.edit_text(f"Üzgünüm, '{query}' ile ilgili bir sonuç bulunamadı.")
                return

            video_info = info['entries'][0]
            
            temp_path_base = ydl.prepare_filename(video_info).rsplit('.', 1)[0]
            downloaded_file = temp_path_base + '.mp3'
            
            await initial_message.edit_text(f"'{video_info.get('title', 'Müzik')}' bulunuyor. İndirme başlatıldı...")
            
            # İndirme işlemi
            ydl.download([video_info['webpage_url']])

        # 3. İndirme başarılı ise: Yüklemeyi ayrı bir senkronize thread içinde başlat
        if os.path.exists(downloaded_file):
            await initial_message.edit_text(f"Şarkı indirildi: {video_info.get('title', 'Bilinmeyen Şarkı')}. Yükleniyor...")
            
            # Yüklemeyi ayrı bir iş parçacığında çalıştırarak ana döngüyü rahatlatıyoruz
            thread = threading.Thread(
                target=_send_audio_sync, 
                args=(update.message.chat_id, downloaded_file, video_info)
            )
            thread.daemon = True # Ana program kapandığında thread'in de kapanmasını sağlar
            thread.start()
            
        else:
            await initial_message.edit_text(f"İndirme tamamlandı ancak dosya yolu bulunamadı: {downloaded_file}")

    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp indirme hatası: {e}")
        if initial_message:
            await initial_message.edit_text(f"❌ İndirme Başarısız: '{query}' ile ilgili bir sorun oluştu (URL geçersiz, bölge kısıtlaması vb.).")
    except Exception as e:
        logger.error(f"Genel hata oluştu: {e}")
        if initial_message:
            await initial_message.edit_text(
                f"❌ İşlem Başarısız: Beklenmedik bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            )

# =================================================================
# 3. WEBHOOK ENTEGRASYONU (FLASK)
# =================================================================

# Flask'ın /webhook_path adresine POST isteği geldiğinde çalışır
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    """Telegram'dan gelen tüm güncellemeleri asenkron olarak işler."""
    
    # Kurulum tamamlanmadıysa isteği reddet
    if not BOT_SETUP_DONE or not application:
        logger.warning("Bot kurulumu tamamlanmadı. İstek göz ardı ediliyor.")
        return jsonify({"status": "setup_not_complete"}), 200

    try:
        json_data = await request.get_json(force=True)
        update = telegram.Update.de_json(json_data, application.bot)
        
        # Güncellemeyi işle
        await application.process_update(update)
        
        # Telegram'a hemen 'ok' yanıtını göndererek zaman aşımını önleriz
        return "ok"
    except Exception as e:
        logger.error(f"Webhook isteği işlenirken kritik hata oluştu: {e}")
        # Hata durumunda 500 kodu, Telegram'a tekrar denemesini söyler
        return Response("Webhook Error", status=500)

# Durum kontrolü için basit bir rota
@app.route('/', methods=['GET'])
def index():
    """Render'ın servisi kontrol etmesi için bir sağlık kontrolü (health check) rotası."""
    status = "OK" if BOT_SETUP_DONE else "Setup Pending"
    return jsonify({"status": status, "webhook_url": WEBHOOK_URL}), 200


# =================================================================
# 4. UYGULAMA BAŞLATMA VE WEBHOOK KURULUMU - NİHAİ YÖNTEM
# =================================================================

async def _internal_setup_webhook():
    """Bot başlatma ve Webhook kurma işlemini asenkron olarak yapar."""
    global application, BOT_SETUP_DONE
    
    await application.initialize()
    
    try:
        if WEB_SERVICE_URL:
            # Eski webhook'u sil ve yenisini kur
            await application.bot.delete_webhook()
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"✅ Webhook başarıyla ayarlandı! URL: {WEBHOOK_URL}")
            BOT_SETUP_DONE = True # Başarılı kurulumu işaretle
        else:
            logger.error("❌ WEB_SERVICE_URL çevresel değişkeni tanımlı değil!")
    except Exception as e:
        logger.error(f"❌ Webhook ayarlanırken kritik hata oluştu: {e}")
        
    await application.start()
    logger.info("Bot arka plan görevleri başlatıldı.")

def setup_bot_sync():
    """Senkronize olarak bot kurulumunu başlatır."""
    global application
    
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sarki", search_and_send_music))
    
    # Asenkron kurulumu senkronize olarak çalıştır (Sadece bir kez!)
    try:
        asyncio.run(_internal_setup_webhook())
    except RuntimeError as e:
        # Daha önceki 'Event loop closed' hatasını görmezden gelerek kurulumun tamamlandığını varsayarız.
        if "Event loop closed" in str(e):
             logger.warning("Bot kurulumu tamamlandı (Event loop uyarısı ile). Devam ediliyor.")
             global BOT_SETUP_DONE
             BOT_SETUP_DONE = True
        else:
            raise e
    
# Ana blok: Botu ve Flask'ı başlat
if __name__ == "__main__":
    
    # Adım 1: Botu Flask başlamadan önce kur
    try:
        setup_bot_sync()
    except Exception as e:
        logger.error(f"Kritik BOT KURULUMU BAŞARISIZ OLDU, Çıkılıyor: {e}")
        # Uygulama bu aşamada tamamen kilitlenirse Render hatayı yakalayacaktır
        exit(1)
            
    # Adım 2: Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask sunucusu başlatılıyor, Port: {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
