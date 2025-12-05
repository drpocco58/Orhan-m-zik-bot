import os
import asyncio
import tempfile
import shutil
import yt_dlp
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("BOT_TOKEN yok. Render env'e BOT_TOKEN ekle.")

# Daha sağlam yt-dlp ayarları
BASE_YDL_OPTS = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "retries": 3,
    "fragment_retries": 3,
    "sleep_interval": 1,
    "max_sleep_interval": 3,
    "source_address": "0.0.0.0",  # IPv4
    # "cookiefile": "cookies.txt",  # varsa aç
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
}

# Yedek API (mucize.ml) — YouTube çalışmazsa buraya düşer
def download_via_mucize(query, tmpdir):
    try:
        url = f"https://api-v2.mucize.ml/mp3?query={requests.utils.quote(query)}"
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            path = os.path.join(tmpdir, "mucize.mp3")
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    except Exception:
        pass
    return None

def _sync_search_and_download(query: str, ydl_base_opts: dict):
    """
    1) Önce ytsearch1 ile arar ve mp3'e dönüştürür.
    2) Eğer sonuç yoksa mucize API'ye düşer.
    Döner: (mp3_path or None, title or None)
    """
    tmpdir = tempfile.mkdtemp(prefix="orhan_")
    opts = dict(ydl_base_opts)
    opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")

    # Try multiple ytsearch variants
    search_prefixes = ["ytsearch1:", "ytsearch:", "ytsearchdate1:"]
    try:
        for pref in search_prefixes:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"{pref}{query}", download=True)
                    # info can be dict with entries
                    entry = None
                    if isinstance(info, dict) and "entries" in info and info["entries"]:
                        entry = info["entries"][0]
                    elif isinstance(info, dict) and info.get("webpage_url"):
                        entry = info
                    if entry:
                        # find downloaded audio file
                        for fname in os.listdir(tmpdir):
                            if fname.lower().endswith((".mp3", ".m4a", ".webm", ".wav", ".aac", ".opus")):
                                return os.path.join(tmpdir, fname), entry.get("title") or query
            except Exception:
                # next search strategy
                continue

        # Eğer YouTube'dan gelmediyse yedek API deneyelim
        muc = download_via_mucize(query, tmpdir)
        if muc:
            return muc, query

        return None, None
    except Exception:
        return None, None

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.message.text or "").strip()
    if not query:
        await update.message.reply_text("Şarkı adını yaz kardeş.")
        return

    status = await update.message.reply_text(f"Aranıyor: {query} 🔎")

    loop = asyncio.get_running_loop()
    try:
        coro = loop.run_in_executor(None, _sync_search_and_download, query, BASE_YDL_OPTS)
        mp3_path, title = await asyncio.wait_for(coro, timeout=180)

        if not mp3_path:
            await status.edit_text("Şarkı bulunamadı (YouTube/Yedek API başarısız).")
            return

        await status.edit_text("Gönderiliyor… 🚀")
        with open(mp3_path, "rb") as f:
            await context.bot.send_audio(chat_id=update.effective_chat.id, audio=f, title=title or query, timeout=300)
        await status.delete()

    except asyncio.TimeoutError:
        await status.edit_text("İndirme çok uzun sürdü (zaman aşımı).")
    except Exception as e:
        await status.edit_text(f"Beklenmeyen hata: {e}")
    finally:
        try:
            if 'mp3_path' in locals() and mp3_path and os.path.exists(mp3_path):
                # mp3_path may be inside tmpdir; remove tmpdir
                shutil.rmtree(os.path.dirname(mp3_path), ignore_errors=True)
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam Orhan usta! Şarkı adını yaz, ben indirmeye çalışayım.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot polling başlatılıyor...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
