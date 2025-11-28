import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from yt_dlp import YoutubeDL
import asyncio

# Render'da gerekli olan kütüphaneler bunlar olduğu için Flask kaldırıldı.

# Token'ı Ortam Değişkenlerinden çekiyoruz.
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    # Render üzerinde hata mesajı verir
    print("HATA: BOT_TOKEN ayarlanmamış. Lütfen Render Ayarları'nı kontrol edin.")
    exit()

# Günlükleme ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Yardımcı Fonksiyon: Şarkıyı Bulma ve İndirme ---
async def arama_ve_indir(query: str) -> tuple | None:
    """Arama yapar, MP3 indirir ve dosya yolunu döner."""

    # DÜŞÜK KALİTE VE ZAMAN AŞIMI AYARLARI (Render'da hızlı indirme için kritik)
    ydl_opts = {
        'format': 'worstaudio/worst', # DÜŞÜK KALİTE (En hızlı indirme için)
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

        # AGRESİF ZAMAN AŞIMI AYARLARI
        'socket_timeout': 5,  # Bağlantı zaman aşımını 5 saniyeye düşür
        'retries': 3,         # Tekrar deneme
        'fragment_retries': 3,
        'geo_bypass': True,
    }

    try:
        # Arama yapmak için YoutubeDL'i kullan
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
    mesaj = await update.message.reply_text(f"🎧 '{arama_metni}' aranıyor ve indiriliyor... Lütfen bekleyin.")

    # Şarkıyı bulma ve indirme işlemini başlat
    sonuc = await asyncio.to_thread(arama_ve_indir, arama_metni) 

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


# --- Ana Fonksiyon ---
def main() -> None:
    """Botu çalıştıran ana fonksiyon."""

    # Render'da botun sürekli çalışmasını sağlamak için Flask'a gerek yoktur.
    # Doğrudan Telegram polling başlatılır.

    # Uygulama oluşturma ve token'ı ekleme
    application = Application.builder().token(BOT_TOKEN).build()

    # /sarki komutunu, sarki_bul fonksiyonuna bağla
    application.add_handler(CommandHandler("sarki", sarki_bul))

    # Botu başlat (Sürekli dinleme)
    print("Bot dinlemede...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
