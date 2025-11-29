import os
import logging
import asyncio
import tempfile
import yt_dlp
import telegram
from flask import Flask, request
from telegram.ext import Application, CommandHandler
from werkzeug.wrappers import Response

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

# Webhook yolları
WEBHOOK_PATH = f'/{BOT_TOKEN}' 
WEBHOOK_URL = WEB_SERVICE_URL + WEBHOOK_PATH

# Flask uygulamasını başlat
app = Flask(__name__)

# Global bot uygulama nesnesi
application: Application = None

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
    
    if not context.args:
        await update.message.reply_text("Lütfen bir şarkı adı ve sanatçı belirtin.\nÖrnek: /sarki Tarkan Kuzu Kuzu")
        return

    query = " ".join(context.args)
    # İlk mesajı anında göndererek kullanıcıya beklediğini bildir.
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
        # İndirme yolunu geçici bir dizine ayarlıyoruz
        'outtmpl': os.path.join(temp_dir, 'music_%(id)s.%(ext)s'), 
        'limit_rate': '1M', 
        'logger': logger 
    }
    
    try:
        # 1. YouTube'dan bilgiyi al ve indir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            
            if 'entries' not in info or not info['entries']:
                await initial_message.edit_text(f"Üzgünüm, '{query}' ile ilgili bir sonuç bulunamadı.")
                return

            video_info = info['entries'][0]
            
            # 2. Dosya adını belirle ve indir
            temp_path_base = ydl.prepare_filename(video_info).rsplit('.', 1)[0]
            downloaded_file = temp_path_base + '.mp3'
            
            await initial_message.edit_text(f"'{video_info.get('title', 'Müzik')}' bulunuyor. İndirme başlatıldı...")
            ydl.download([video_info['webpage_url']])

        # 3. Telegram'a gönder
        if os.path.exists(downloaded_file):
            await initial_message.edit_text(f"Şarkı bulundu: {video_info.get('title', 'Bilinmeyen Şarkı')}. Gönderiliyor...")
            
            with open(downloaded_file, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=video_info.get('title', 'Bilinmeyen Şarkı'),
                    performer=video_info.get('artist', video_info.get('channel', 'Bilinmeyen Sanatçı')),
                    caption="Müziğiniz hazır! Bizi kullandığınız için teşekkürler."
                )
            await initial_message.delete()
        else:
            await initial_message.edit_text(f"İndirme başarılı oldu ancak dosya yolu bulunamadı: {downloaded_file}")

    except Exception as e:
        logger.error(f"İndirme veya gönderme sırasında hata: {e}")
        await initial_message.edit_text(
            f"❌ İşlem Başarısız: '{query}' ile ilgili bir sonuç bulunamadı veya indirme sırasında beklenmedik bir hata oluştu. Detay: {e}"
        )
    finally:
        # 4. Temizleme
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            logger.info(f"Geçici dosya silindi: {downloaded_file}")

# =================================================================
# 3. WEBHOOK ENTEGRASYONU (FLASK)
# =================================================================

# Flask'ın /webhook_path adresine POST isteği geldiğinde çalışır
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    """Telegram'dan gelen tüm güncellemeleri asenkron olarak işler."""
    
    # Flask'ın isteği asenkron olarak işlemesi için gereken dönüşümü yap
    try:
        json_data = await request.get_json(force=True)
        update = telegram.Update.de_json(json_data, application.bot)
        
        # Güncellemeyi işle
        await application.process_update(update)
        
        return "ok"
    except Exception as e:
        logger.error(f"Webhook isteği işlenirken hata oluştu: {e}")
        return Response("Webhook Error", status=500)

# =================================================================
# 4. UYGULAMA BAŞLATMA VE WEBHOOK KURULUMU - NİHAİ YÖNTEM
# =================================================================

async def setup_webhook():
    """Webhook'u ayarlar ve botun başlatma işlemlerini yapar."""
    
    # 1. Başlatma
    await application.initialize()
    
    # 2. Webhook'u ayarla
    try:
        if WEB_SERVICE_URL:
            # Önce eski webhook'u kaldır, sonra yenisini kur
            await application.bot.delete_webhook()
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"✅ Webhook başarıyla ayarlandı! URL: {WEBHOOK_URL}")
        else:
            logger.error("❌ WEB_SERVICE_URL çevresel değişkeni tanımlı değil!")
    except Exception as e:
        logger.error(f"❌ Webhook ayarlanırken kritik hata oluştu: {e}")
        
    # 3. Arka plan görevlerini başlat
    await application.start()
    logger.info("Bot arka plan görevleri başlatıldı.")

# Ana blok: Botu ve Flask'ı başlat
if __name__ == "__main__":
    
    # Global application objesini tanımla
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # İşleyicileri (handlers) ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sarki", search_and_send_music))

    # Tüm asenkron kurulumu senkronize bir şekilde çalıştır (Webhook ayarlanmasını GARANTİ EDER)
    # Bu, Flask başlamadan önce botun hazır olmasını sağlar.
    # NOT: Bu bloğun başarısız olması, Flask'ın hiç başlamamasına neden olur. Başarılı olması GEREKİR.
    try:
        asyncio.run(setup_webhook())
    except Exception as e:
        logger.error(f"BOT KURULUMU BAŞARISIZ OLDU: {e}")
        # Kurulum başarısız olsa bile Flask'ı başlatmaya devam et (servisin ayakta kalması için)
        pass 
    
    # Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask sunucusu başlatılıyor, Port: {port}")
    
    # Flask'ın kendi senkron sunucusunu başlat
    app.run(host='0.0.0.0', port=port, debug=False)
