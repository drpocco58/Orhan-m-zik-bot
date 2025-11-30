import os
import logging
import json
import time
from flask import Flask, request
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from telegram import Update, Bot
from yt_dlp import YoutubeDL

# Gerekli kütüphaneleri içe aktarın (Eğer kullandığınız Flask uygulamasında 'logger' tanımlı değilse, bu satırı kullanın)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Çevre değişkenlerinden Telegram Bot Token'ını alın
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN çevresel değişkeni bulunamadı. Lütfen Render ayarlarınızı kontrol edin.")

# Bot ve Dispatcher kurulumu
bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# ----------------------------------------
# 1. BOT KOMUTLARI
# ----------------------------------------

def start(update, context):
    """/start komutunu işler."""
    update.message.reply_text('Merhaba! Ben bir müzik botuyum. Şarkı indirmek için /sarki <Sanatçı Adı - Şarkı Adı> komutunu kullanın.')

def help_command(update, context):
    """/help komutunu işler."""
    update.message.reply_text('Kullanım: /sarki <Sanatçı Adı - Şarkı Adı>. Örnek: /sarki Emrah unutabilsen')

def download_song(update, context):
    """Kullanıcının isteği üzerine YouTube'dan şarkıyı arar ve indirir."""
    
    # Komut argümanlarını kontrol et
    if not context.args:
        update.message.reply_text("Lütfen şarkı adını belirtin. Kullanım: /sarki <Sanatçı Adı - Şarkı Adı>")
        return

    query = " ".join(context.args)
    
    # Kullanıcıya işlem başladığını bildir
    update.message.reply_text(f'"{query}" aranıyor ve indirilmeye hazırlanıyor. Lütfen bekleyin...')
    
    try:
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
                update.message.reply_audio(
                    f, 
                    caption=f'İşte "{entry.get("title", "Şarkı")}"',
                    title=entry.get("title", "Şarkı")
                )
            
            # 3. İndirilen dosyayı sunucudan sil (Render kısıtlamaları nedeniyle)
            os.remove(audio_file)
            logger.info(f"Dosya başarıyla gönderildi ve silindi: {audio_file}")
            
        else:
            update.message.reply_text("Üzgünüm, şarkı indirilemedi veya dosya bulunamadı.")
            logger.warning(f"İndirilemedi: {audio_file}")

    except Exception as e:
        logger.error(f"Şarkı indirme hatası: {e}")
        update.message.reply_text('Üzgünüm, şarkıyı ararken veya indirirken bir hata oluştu.')
        
# ----------------------------------------
# 2. KOMUT İŞLEYİCİLERİ (HANDLERS)
# ----------------------------------------

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("sarki", download_song))

# ----------------------------------------
# 3. WEBHOOK VE SUNUCU KURULUMU (Render Uyumlu)
# ----------------------------------------

# Telegram'dan gelen POST isteklerini bu adrese yönlendiriyoruz
@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def webhook():
    """Telegram'dan gelen Webhook güncellemelerini işler."""
    if request.method == "POST":
        # Gelen JSON verisini Telegram'ın anlayacağı Update nesnesine çevirir.
        update = Update.de_json(request.get_json(force=True), bot)
        
        # Güncellemeyi (mesajı) ana komut işleyicinize (dispatcher) yönlendirir.
        dispatcher.process_update(update)

    return 'OK' # Telegram'a mesajın başarılı bir şekilde alındığını bildirir.

# Flask uygulamasının Render ortamında başlatılması için gerekli fonksiyon
def run():
    """Uygulamayı Render tarafından belirlenen portta başlatır."""
    port = int(os.environ.get("PORT", 5000))
    # Flask uygulamasını belirlenen portu dinlemesi için çalıştır
    logger.info(f"Flask uygulaması 0.0.0.0:{port} adresinde başlatılıyor.")
    app.run(host='0.0.0.0', port=port)

# Uygulamanın başlatılması
if __name__ == '__main__':
    # Bu blok, uygulamanın Render tarafından başlatılmasını sağlar.
    # Bu, en son yaptığımız ve port hatasını çözen ayardır.
    run()

# Gunicorn çalıştırıldığında burası tetiklenir ve port ayarı için Flask'ı kullanır.
