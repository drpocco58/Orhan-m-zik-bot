import os
import asyncio
import tempfile
import shutil
import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# TOKEN environment'dan alınıyor
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("BOT_TOKEN environment variable yok. Render ayarlarına BOT_TOKEN ekle.")

# Genel yt-dlp seçenekleri (her indirme kendi outtmpl ile ayrı klasöre yazılır)
BASE_YDL_OPTS = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
    # "cookiefile": "cookies.txt",   # varsa ekleyebilirsin
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam Orhan usta! Bana şarkı adı gönder, MP3 yapıp göndereyim. 🎶")


def _sync_download_search_to_mp3(query: str, ydl_base_opts: dict):
    """
    Synchronous function to run inside executor.
    Creates a temp dir, downloads the best audio and converts to mp3,
    returns (mp3_path, temp_dir) or (None, temp_dir) on failure.
    """
    tmpdir = tempfile.mkdtemp(prefix="orhan_")
    opts = dict(ydl_base_opts)
    opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            # get entry used (search returns entries)
            entry = None
            if isinstance(info, dict) and "entries" in info and info["entries"]:
                entry = info["entries"][0]
            elif isinstance(info, dict):
                entry = info
            # find a file inside tmpdir that looks like audio
            for fname in os.listdir(tmpdir):
                if fname.lower().endswith((".mp3", ".m4a", ".webm", ".wav", ".aac", ".opus")):
                    return os.path.join(tmpdir, fname), tmpdir
            return None, tmpdir
    except Exception as e:
        # ensure tmpdir left for cleanup by caller
        return None, tmpdir


async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.message.text or "").strip()
    if not query:
        await update.message.reply_text("Şarkı adını yaz usta.")
        return

    status_msg = await update.message.reply_text(f"Aranıyor: {query} 🔎")
    loop = asyncio.get_running_loop()

    try:
        # çalıştırma için 120s timeout (gerekirse artır)
        coro = loop.run_in_executor(None, _sync_download_search_to_mp3, query, BASE_YDL_OPTS)
        mp3_path, tmpdir = await asyncio.wait_for(coro, timeout=120)

        if not mp3_path or not os.path.exists(mp3_path):
            await status_msg.edit_text("Şarkı bulunamadı veya indirme başarısız oldu.")
            return

        await status_msg.edit_text("Gönderiliyor… 🚀")

        # Telegram'a gönder (dosya olarak)
        with open(mp3_path, "rb") as f:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=f,
                title=os.path.basename(mp3_path).rsplit(".", 1)[0],
                timeout=300
            )

        await status_msg.delete()

    except asyncio.TimeoutError:
        await status_msg.edit_text("İndirme çok sürdü (zaman aşımı). Başka şarkı dene.")
    except Exception as e:
        await status_msg.edit_text(f"Hata oldu: {e}")
    finally:
        # tmpdir temizle (varsa)
        try:
            if 'tmpdir' in locals() and tmpdir and os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
        except Exception:
            pass


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    # run_polling() bloklayıcıdır ve process'i ayakta tutar
    print("Bot polling modunda başlatılıyor...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
