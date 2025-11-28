import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from yt_dlp import YoutubeDL
import asyncio
from flask import Flask, request, jsonify # Webhook için flask geri geldi!
import threading

# Token ve URL'leri Ortam Değişkenlerinden çekiyoruz.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Render, URL'yi otomatik olarak "WEB_SERVICE_URL" ortam değişkenine yazar
WEB_SERVICE_URL = os.environ.get("WEB_SERVICE_URL") 
PORT = int(os.environ.get("PORT", 5000)) # Render'ın vereceği portu kullan

if not BOT_TOKEN or not WEB_SERVICE_URL:
    print("HATA: BOT_TOKEN veya WEB_SERVICE_URL ayarlanmamış. Lütfen Render Ayarları'nı kontrol edin.")
    exit()

# Günlükleme ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask uygulaması
app = Flask(__name__)
application = None # Global application değişkeni

# --- Yardımcı Fonksiyon: Şarkıyı Bulma ve İndirme ---
# NOT: ffmpeg-python kütüphanesi pyproject.toml'a eklendiği için artık yt-dlp bu kütüphaneyi kullanabilir.
async def arama_ve_indir(query: str) -> tuple | None:
    """Arama yapar, MP3 indirir ve dosya yolunu döner."""

    # DÜŞÜK KALİTE VE ZAMAN AŞIMI AYARLARI
    ydl_opts = {
        'format': 'worstaudio/worst', 
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64', # MP3 Kalitesi 64kbps
        }],
        'outtmpl': 'downloaded_song.%(ext)s', 
        'noplaylist': True,
        'quiet': True,
        'nocheckcertificate': True,
        'default_search': 'ytsearch',

        # ZAMAN AŞIMI AYARLARI
        'socket_timeout': 5, 
        'retries': 3,         
        'fragment_retries': 3,
        'geo_bypass': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Şarkıyı arat ve bilgiyi al (Sadece 1 sonuç)
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or not info.get('entries'):
                logger.warning(f"Arama sonuç vermedi: {query}")
                return None

            # İndirilen dosyanın ismini ve yolunu bulma
            dosya_ismi = ydl.prepare_filename(info['entries'][0])
            dosya_yolu = dosya_ismi.rsplit('.', 1)[0] + '.mp3'

            title = info['entries'][0].get('title', 'Bilinmeyen Şarkı')

            return (dosya_yolu, title)

    except Exception as e:
        logger.error(f"İndirme/Arama sırasında hata: {e}")
        return None

# Webhook'un indirme işlemini beklemesini sağlayan senkronize sarıcı
# Bu sayede uzun süren indirme işlemi Telegram'a "timeout" hatası vermeden yapılır.
def arama_ve_indir_sync(query: str):
    return asyncio.run(arama_ve_indir(query))

# --- Telegram Komut İşleyicisi ---
async def sarki_bul(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcıdan gelen /sarki komutunu işler."""
    
    arama_metni = ' '.join(context.args)

    if not arama_metni:
        await update.message.reply_text(
            "Lütfen bir şarkı veya sanatçı ismi yazın! Örn: /sarki Tarkan Kuzu Kuzu"
        )
        return

    # Hemen cevap ver, indirme işleminin başladığını bildir
    mesaj = await update.message.reply_text(f"🎧 '{arama_metni}' aranıyor ve indiriliyor... Bu işlem biraz zaman alabilir.")

    # Şarkıyı bulma ve indirme işlemini başlat (Ayrı bir Thread'de)
    loop = asyncio.get_event_loop()
    # run_in_executor sayesinde indirme işlemi ana döngüyü bloklamaz.
    sonuc = await loop.run_in_executor(None, arama_ve_indir_sync, arama_metni)

    # HATA KONTROLÜ
    if not sonuc or not isinstance(sonuc, tuple) or len(sonuc) != 2:
        await mesaj.edit_text(f"❌ Üzgünüm, '{arama_metni}' ile ilgili bir sonuç bulunamadı veya indirme hatası oluştu.")
        return

    dosya_yolu, sarkı_başlığı = sonuc

    try:
        # MP3 dosyasını gruba gönder
        with open(dosya_yolu, 'rb') as f:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id, 
                audio=f, 
                caption=f"🎶 **Şarkı bulundu:** {sarkı_başlığı}\nİsteğiniz üzerine gönderildi.",
                parse_mode='Markdown'
            )

        # Başlangıç mesajını sil
        await mesaj.delete()

    except Exception as e:
        logger.error(f"Telegram'a dosya gönderirken hata: {e}")
        await mesaj.edit_text(f"❌ Şarkı indirildi ancak gönderilemedi. Hata: {e}")

    finally:
        # Sunucudan indirdiğimiz dosyayı temizle
        if os.path.exists(dosya_yolu):
            os.remove(dosya_yolu)


# --- Webhook İstemcisi ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    """Telegram'dan gelen mesajları işleyen webhook."""
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # Handler'ı ayrı bir thread'de çalıştırma 
        await application.update_queue.put(update)

        # Telegram'a hemen cevap veriyoruz (200 OK)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook hatası: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def home():
    """Render'ın web hizmetini kontrol etmesi için basit bir sayfa."""
    return "Bot is running via Webhook!"


# --- Ana Fonksiyon ---
def main() -> None:
    """Botu çalıştıran ana fonksiyon."""
    global application
    
    # Uygulama oluşturma
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Komutları ekle
    application.add_handler(CommandHandler("sarki", sarki_bul))

    # Telegram'a Webhook URL'sini ayarla
    webhook_url = f"{WEB_SERVICE_URL.rstrip('/')}/{BOT_TOKEN}"
    application.bot.set_webhook(url=webhook_url)

    # Bot işlemleri için sadece başlatma (artık Polling yok!)
    def start_bot_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Sadece post_init çağrılır. Polling veya Webhook dinleme yapılmaz.
        # Dinleme işini Flask halleder.
        loop.run_until_complete(application.post_init())

    threading.Thread(target=start_bot_worker).start()

    # Flask uygulamasını başlat
    print(f"Flask Webhook dinlemede: {WEB_SERVICE_URL}:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
