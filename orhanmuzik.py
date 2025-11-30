import os
import logging
import json
import time
from flask import Flask, request
# !!! BURASI DEĞİŞTİ: Yeni versiyona uyum sağlamak için importlar güncellendi !!!
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update, Bot

# Gerekli kütüphaneleri içe aktarın
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Çevre değişkenlerinden Telegram Bot Token'ını alın
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN çevresel değişkeni bulunamadı. Lütfen Render ayarlarınızı kontrol edin.")

# Flask uygulaması kurulumu (Application nesnesi Dispatcher'ın yerini aldı)
app = Flask(__name__)
# ApplicationBuilder ile bot nesnesi oluşturulur ve Application başlatılır
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
bot = application.bot

# ----------------------------------------
# 1. BOT KOMUTLARI (ContextTypes.DEFAULT_TYPE ile uyumlu hale getirildi)
# ----------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutunu işler."""
    await update.message.reply_text('Merhaba! Ben bir müzik botuyum. Şarkı indirmek için /sarki <Sanatçı Adı - Şarkı Adı> komutunu kullanın.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help komutunu işler."""
    await update.message.reply_text('Kullanım: /sarki <Sanatçı Adı - Şarkı Adı>. Örnek: /sarki Emrah unutabilsen')

async def download_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının isteği üzerine YouTube'dan şarkıyı arar ve indirir."""
    
    # Komut argümanlarını kontrol et
    if not context.args:
        await update.message.reply_text("Lütfen şarkı adını belirtin. Kullanım: /sarki <Sanatçı Adı - Şarkı Adı>")
        return

    query = " ".join(context.args)
    
    # Kullanıcıya işlem başladığını bildir
    await update.message.reply_text(f'"{query}" aranıyor ve indirilmeye hazırlanıyor. Lütfen bekleyin...')
    
    try:
        # yt-dlp import'u kodun en tepesine taşınmıştır.
        from yt_dlp import YoutubeDL 
        
        # 1. YT-DLP Ayarları
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',  # İndirilen dosyayı downloads klasörüne kaydet
            'quiet': True,
            'default_search': 'ytsearch', # Varsayılan olarak YouTube'da ara
            'max_downloads': 1 # Sadece ilk sonucu indir
        }
        
        # downloads klasörünün varlığını kontrol et ve oluştur
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with YoutubeDL(ydl_opts) as ydl:
            # Şarkıyı ara ve indir
            info_dict = ydl.extract_info(query, download=True)
            
            # İndirilen dosyanın yolunu bul
            if 'entries' in info_dict and info_dict['entries']:
                # Tek bir giriş olması beklenir
                entry = info_dict['entries'][0]
            else:
                entry = info_dict
                
            # İndirilen dosyanın gerçek yolunu almak için dosya adını yeniden oluştur
            filename = ydl.prepare_filename(entry)
            audio_file = filename.rsplit('.', 1)[0] + '.mp3' 

        if os.path.exists(audio_file):
            # 2. Şarkıyı Telegram'a Gönder
            with open(audio_file, 'rb') as f:
                await update.message.reply_audio(
                    f, 
                    caption=f'İşte "{entry.get("title", "Şarkı")}"',
                    title=entry.get("title", "Şarkı")
                )
            
            # 3. İndirilen dosyayı sunucudan sil (Render kısıtlamaları nedeniyle)
            os.remove(audio_file)
            logger.info(f"Dosya başarıyla gönderildi ve silindi: {audio_file}")
            
        else:
            await update.message.reply_text("Üzgünüm, şarkı indirilemedi veya dosya bulunamadı.")
            logger.warning(f"İndirilemedi: {audio_file}")

    except Exception as e:
        logger.error(f"Şarkı indirme hatası: {e}")
        await update.message.reply_text('Üzgünüm, şarkıyı ararken veya indirirken bir hata oluştu.')
        
# ----------------------------------------
# 2. KOMUT İŞLEYİCİLERİ (HANDLERS)
# ----------------------------------------

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("sarki", download_song))

# ----------------------------------------
# 3. WEBHOOK VE SUNUCU KURULUMU (Application nesnesine uyarlandı)
# ----------------------------------------

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
async def webhook():
    """Telegram'dan gelen Webhook güncellemelerini işler."""
    if request.method == "POST":
        # Yeni PTB'de process_update yerini update.de_json alıyor.
        update = Update.de_json(request.get_json(force=True), bot)
        
        # Application'ın update'i işlemesi için async kullanımı zorunludur.
        await application.process_update(update)

    return 'OK' # Telegram'a mesajın başarılı bir şekilde alındığını bildirir.

# Flask uygulamasının Render ortamında başlatılması için gerekli fonksiyon
def run():
    """Uygulamayı Render tarafından belirlenen portta başlatır."""
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Flask uygulaması 0.0.0.0:{port} adresinde başlatılıyor.")
    app.run(host='0.0.0.0', port=port)

# Uygulamanın başlatılması (Gunicorn, bu dosyayı başlatır)
# NOT: Artık uygulama, Gunicorn tarafından başlatılacağı için 'if __name__ == "__main__":' bloğu Gunicorn komutunu bozmasın diye kaldırılmıştır.
