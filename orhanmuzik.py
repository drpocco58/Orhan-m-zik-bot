import os
import logging
import asyncio
import tempfile
import yt_dlp
import requests
import telegram
# Web sunucusu için gerekli kütüphaneler
from flask import Flask, request
from telegram.ext import Application, CommandHandler

# Yapılandırma
# Loglama seviyesini INFO olarak ayarla
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Çevre değişkenlerini al
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Render tarafından sağlanan hizmet URL'si (Örn: https://drmuzik-bot-1.onrender.com)
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL") 
# Webhook yolu
WEBHOOK_PATH = f'/{BOT_TOKEN}' 
# Webhook'un tam URL'si
WEBHOOK_URL = WEB_SERVICE_URL + WEBHOOK_PATH

# Flask uygulamasını başlat
app = Flask(__name__)

# Global bot uygulama nesnesi
application: Application = Application.builder().token(BOT_TOKEN).build()


# Bot komutları ve işlevleri

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

    # Arama sorgusunu oluştur
    query = " ".join(context.args)
    
    # Gönderim başarılı olana kadar bekleyen bir mesaj gönder
    initial_message = await update.message.reply_text(f"'{query}' için arama yapılıyor ve indirme başlatılıyor. Lütfen bekleyin...")
    logger.info(f"Yeni istek: {query}")

    # Geçici dosya oluşturma için sistemin geçici dizinini kullan
    temp_dir = tempfile.gettempdir()
    
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
        'limit_rate': '1M', # Hızı 1MB/s ile sınırla (Render'da zaman aşımını önlemek için)
        'logger': logger # Loglama için kendi logger'ımızı kullan
    }

    downloaded_file = None
    
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
            
            # 5. Temizleme
            os.remove(downloaded_file)
            logger.info(f"'{video_info.get('title', 'music')}' başarıyla gönderildi ve silindi.")
        else:
            await initial_message.edit_text(f"İndirme başarılı oldu ancak dosya yolu bulunamadı: {downloaded_file}")

    except Exception as e:
        logger.error(f"İndirme veya gönderme sırasında hata: {e}")
        # Hata durumunda geçici dosyayı temizlemeyi dene
        if downloaded_file and os.path.exists(downloaded_file):
             os.remove(downloaded_file)
             logger.info(f"Hata sonrası geçici dosya silindi: {downloaded_file}")
             
        await initial_message.edit_text(
            f"❌ İşlem Başarısız: '{query}' ile ilgili bir sonuç bulunamadı veya indirme sırasında beklenmedik bir hata oluştu."
            f"\nDetay: {e}"
        )


# Flask Webhook Görünümü
async def telegram_webhook():
    """Telegram'dan gelen tüm güncellemeleri işler."""
    if request.method == "POST":
        # Telegram'dan gelen JSON verisini al ve güncelleme objesine çevir
        update = telegram.Update.de_json(request.get_json(force=True), application.bot)
        
        # Güncellemeyi işleyiciye ilet
        await application.process_update(update)
        
        return "ok"
    return "ok"

# Flask rotalarını bağla
app.add_url_rule(WEBHOOK_PATH, view_func=telegram_webhook, methods=['POST'])

# Uygulama başlatma fonksiyonu
def setup_application():
    """Bot uygulamasını başlatır, işleyicileri ekler ve Webhook'u ayarlar."""
    
    # 1. İşleyicileri (handlers) ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sarki", search_and_send_music))
    
    # 2. Uygulamayı başlat
    # DÜZELTİLDİ: initialize() metodu artık doğru şekilde çağrılıyor.
    # Bu, Application'ın tüm dahili bileşenlerini hazırlar.
    asyncio.run(application.initialize())
    
    # 3. Webhook'u ayarla (Asenkron kodu senkronize çalıştırma)
    asyncio.run(set_webhook_url())

async def set_webhook_url():
    """Botun Webhook'unu Render URL'sine ayarlar."""
    try:
        # Mevcut Webhook'u temizle (varsa)
        await application.bot.delete_webhook()
        # Yeni Webhook'u ayarla
        if WEB_SERVICE_URL:
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"✅ Webhook başarıyla ayarlandı! URL: {WEBHOOK_URL}")
        else:
            logger.error("❌ WEB_SERVICE_URL çevresel değişkeni tanımlı değil!")
    except Exception as e:
        logger.error(f"❌ Webhook ayarlanırken hata oluştu: {e}")


# Ana blok: Botu başlat
if __name__ == "__main__":
    # Uygulama kurulumunu yap (Hata almamak için Flask'tan önce)
    setup_application() 
    
    # Render, portu PORT ortam değişkeni üzerinden sağlar (varsayılan: 10000)
    port = int(os.environ.get("PORT", 10000))
    # Werkzeug sunucusunu başlat
    logger.info(f"Flask sunucusu başlatılıyor, Port: {port}")
    # Flask uygulamasını 0.0.0.0 adresinde ve Render'ın belirlediği portta çalıştır
    app.run(host='0.0.0.0', port=port)
