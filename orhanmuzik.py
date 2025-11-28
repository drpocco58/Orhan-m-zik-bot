import os
import logging
import tempfile
import yt_dlp
import telegram
from flask import Flask, request
from telegram.ext import Application, CommandHandler, PicklePersistence
from telegram.constants import ParseMode

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
# Render URL'si
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL") 
# Webhook yolu (Güvenlik için token kullanıyoruz)
WEBHOOK_PATH = f'/{BOT_TOKEN}' 
# Webhook'un tam URL'si
WEBHOOK_URL = WEB_SERVICE_URL + WEBHOOK_PATH

# Flask uygulamasını başlat
app = Flask(__name__)

# Global bot uygulama nesnesi
# PTB Webhook sunucusunu kullanmak yerine, Flask ile uyumlu bir Application oluşturuyoruz.
# persistence kullanmiyoruz, sadece web server ve botu ayakta tutuyoruz
application: Application = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

# =================================================================
# 2. BOT KOMUTLARI
# =================================================================

async def start_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışır."""
    await update.message.reply_text(
        "Merhaba! Ben Orhan Müzik Botu. İstediğiniz müziği Youtube'dan indirip size gönderebilirim.\n\n"
        "Kullanım: /sarki [Şarkı Adı] [Sanatçı Adı]\n\n"
        "Örnek: /sarki Tarkan Kuzu Kuzu"
    )

async def search_and_send_music(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    """Kullanıcının isteğini alır, YouTube'da arar ve gönderir."""
    
    # 1. Giriş kontrolü
    if not context.args:
        await update.message.reply_text("Lütfen bir şarkı adı ve sanatçı belirtin.\nÖrnek: /sarki Tarkan Kuzu Kuzu")
        return

    query = " ".join(context.args)
    
    # Gönderim başarılı olana kadar bekleyen bir mesaj gönder
    initial_message = await update.message.reply_text(f"'{query}' için arama yapılıyor ve indirme başlatılıyor. Lütfen bekleyin...")
    logger.info(f"Yeni istek: {query}")

    temp_dir = tempfile.gettempdir()
    downloaded_file = None
    video_info = None

    # 2. YouTube indirme seçenekleri
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
        # İndirme yolunu geçici bir dizine ayarlıyoruz
        'outtmpl': os.path.join(temp_dir, 'music_%(id)s.%(ext)s'), 
        'limit_rate': '1M', 
        'logger': logger 
    }
    
    try:
        # 3. Şarkıyı ara ve indir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            
            # 3a. Şarkı bilgisini al
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            
            if 'entries' not in info or not info['entries']:
                await initial_message.edit_text(f"Üzgünüm, '{query}' ile ilgili bir sonuç bulunamadı.")
                return

            video_info = info['entries'][0]
            
            # 3b. Dosyanın adını ve yolunu hesapla (postprocessor sonrası .mp3)
            temp_path_base = ydl.prepare_filename(video_info).rsplit('.', 1)[0]
            downloaded_file = temp_path_base + '.mp3'
            
            # 3c. İndirme işlemini gerçekleştir
            await initial_message.edit_text(f"'{video_info.get('title', 'Müzik')}' bulunuyor. İndirme başlatıldı...")
            ydl.download([video_info['webpage_url']])


        # 4. Telegram'a gönder
        if os.path.exists(downloaded_file):
            
            await initial_message.edit_text(f"Şarkı bulundu: {video_info.get('title', 'Bilinmeyen Şarkı')}. Gönderiliyor...")
            
            # Audio dosyasını ikili (binary) modda aç ve gönder
            with open(downloaded_file, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=video_info.get('title', 'Bilinmeyen Şarkı'),
                    performer=video_info.get('artist', video_info.get('channel', 'Bilinmeyen Sanatçı')),
                    caption="Müziğiniz hazır! Bizi kullandığınız için teşekkürler."
                )
            
            # İlk mesajı sil
            await initial_message.delete()
            
        else:
            await initial_message.edit_text(f"İndirme başarılı oldu ancak dosya yolu bulunamadı: {downloaded_file}")

    except Exception as e:
        logger.error(f"İndirme veya gönderme sırasında hata: {e}")
        await initial_message.edit_text(
            f"❌ İşlem Başarısız: '{query}' ile ilgili bir sonuç bulunamadı veya indirme sırasında beklenmedik bir hata oluştu."
            f"\nDetay: {e}"
        )
    finally:
        # 5. Temizleme (Hata olsa da olmasa da çalışır)
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            logger.info(f"Geçici dosya silindi: {downloaded_file}")

# =================================================================
# 3. WEBHOOK ENTEGRASYONU (FLASK)
# =================================================================

# Flask'ın /webhook_path adresine POST isteği geldiğinde çalışır
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    """Telegram'dan gelen tüm güncellemeleri işler."""
    
    # Gelen JSON verisini al
    json_data = request.get_json(force=True)
    
    # PTB'nin WebhookDispatchingService.process_update metodunu çağırıyoruz.
    # Bu metot, Flask'ın zaten çalışan asenkron döngüsünü kullanır.
    update = telegram.Update.de_json(json_data, application.bot)
    await application.process_update(update)
    
    return "ok"

# =================================================================
# 4. UYGULAMA BAŞLATMA
# =================================================================

async def initialize_and_set_webhook():
    """Application'ı başlatır ve Webhook URL'sini ayarlar."""
    
    # Application'ın temel bileşenlerini asenkron başlat
    # Bu, önceki hataları çözen yegane yoldur.
    await application.initialize()
    
    # Webhook'u ayarla
    if WEB_SERVICE_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Webhook başarıyla ayarlandı! URL: {WEBHOOK_URL}")
    else:
        logger.error("❌ WEB_SERVICE_URL çevresel değişkeni tanımlı değil!")

def setup_bot():
    """Bot işleyicilerini ekler ve PTB uygulaması için temel ayarları yapar."""
    
    # İşleyicileri (handlers) ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sarki", search_and_send_music))
    
    # Asenkron başlatma ve webhook kurma işlemini çalıştır
    # Bu, Flask sunucusu başlamadan önce çalışmalı ve tek bir asyncio.run() çağrısı olmalı.
    try:
        application.updater = initialize_and_set_webhook()
        application.loop.run_until_complete(application.updater)
    except RuntimeError as e:
        logger.warning(f"Asyncio uyarısı (genellikle normaldir): {e}. Webhook ayarları yapılmış olabilir.")
        # Eğer loop zaten çalışıyorsa, (Render'ın iç yapısı nedeniyle olabilir) sadece logla ve devam et.
        # Bu kısım sadece hatayı yutmak için değil, uygulamanın çalışmasını sağlamak için var.

# Ana blok: Botu ve Flask'ı başlat
if __name__ == "__main__":
    
    # 1. Bot ayarlarını yap ve Webhook'u kur
    setup_bot() 
    
    # 2. Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask sunucusu başlatılıyor, Port: {port}")
    
    # Flask uygulamasını 0.0.0.0 adresinde ve Render'ın belirlediği portta çalıştır
    # Debug=False olarak kalmalı
    app.run(host='0.0.0.0', port=port, debug=False)
