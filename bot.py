import os
import subprocess
import glob
from pyrogram import Client, filters
from pyrogram.types import Message

# ------------------- CONFIG -------------------
API_ID = int(os.environ.get("API_ID", 24435985))
API_HASH = os.environ.get("API_HASH", "0fec896446625478537e43906a4829f8")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7662286847:AAEkI_-OQPZck3jhJM6BrKM1JSgp2l43Td4")

# Paths
MULTI_DL_PATH = "/home/ubuntu/Ac"      # cloned repo
VIDEOS_PATH = os.path.join(MULTI_DL_PATH, "videos") # where MDNX stores videos
LOG_PATH = os.path.join(VIDEOS_PATH, "download.log") # log file path

# Ensure folders exist
os.makedirs(VIDEOS_PATH, exist_ok=True)

# ----------------------------------------------
app = Client("crunchyroll_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ------------------- Helper Functions -------------------
def run_mdnx(season_id, episode, dub_lang, dl_subs, default_audio, default_sub, qual):
    """
    Run Multi Downloader NX command for Crunchyroll
    """
    cmd = [
        "npx", "ts-node", "-T", "./index.ts",
        "--service", "crunchy",
        "--srz", season_id,
        "-e", episode,
        "--dubLang", dub_lang,
        "--dlsubs", dl_subs,
        "--defaultAudio", default_audio,
        "--defaultSub", default_sub,
        "--forceMuxer", "mkvmerge",
        "-q", qual
    ]

    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            cwd=MULTI_DL_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            print(line, end="")

        process.wait()

    return process.returncode

# ------------------- Bot Commands -------------------
@app.on_message(filters.command("dl") & filters.private)
async def download_crunchyroll(client: Client, message: Message):
    """
    Download a Crunchyroll episode using Multi Downloader NX
    Command format:
    /dl <season_id> <episode> <dubLang> <subs> <defaultAudio> <defaultSub> <quality>
    """
    cmd_args = message.text.split()
    if len(cmd_args) < 8:
        await message.reply_text(
            "Usage:\n/dl <season_id> <episode> <dubLang> <subs> <defaultAudio> <defaultSub> <quality>"
        )
        return

    season_id, episode, dub_lang, dl_subs, default_audio, default_sub, qual = cmd_args[1:8]

    await message.reply_text(f"🎬 Starting download for episode {episode} of season {season_id}...")

    # ------------------- Ensure Session Initialized -------------------
    session_file = os.path.join(MULTI_DL_PATH, "session.json")
    if not os.path.exists(session_file):
        await message.reply_text("🔑 No session found, auto-login initializing...")
        login_cmd = [
            "npx", "ts-node", "-T", "./index.ts",
            "--service", "crunchy",
            "--autoLogin",
            "--verbose"
        ]
        subprocess.run(login_cmd, cwd=MULTI_DL_PATH)

    # ------------------- Run Downloader -------------------
    try:
        returncode = run_mdnx(season_id, episode, dub_lang, dl_subs, default_audio, default_sub, qual)
        if returncode == 0:
            await message.reply_text("✅ Download finished successfully!")
        else:
            await message.reply_text("❌ Download failed! Check the log for details.")
    except Exception as e:
        await message.reply_text(f"⚠️ Error while running downloader:\n{e}")

    # ------------------- Send Log File -------------------
    try:
        await message.reply_document(LOG_PATH, caption="🧾 Download Log")
    except Exception as e:
        await message.reply_text(f"⚠️ Couldn't send log file:\n{e}")

    # ------------------- Find Downloaded Video -------------------
    video_files = glob.glob(os.path.join(VIDEOS_PATH, "**/*.mkv"), recursive=True)
    video_files += glob.glob(os.path.join(VIDEOS_PATH, "**/*.mp4"), recursive=True)

    if not video_files:
        await message.reply_text("⚠️ No video found to upload.")
        return

    # Pick the newest file
    video_file = max(video_files, key=os.path.getmtime)
    file_name = os.path.basename(video_file)

    await message.reply_text(f"📤 Uploading `{file_name}` to Telegram...")

    try:
        await message.reply_document(video_file, caption=f"🎥 {file_name}")
        await message.reply_text("✅ Upload complete!")
    except Exception as e:
        await message.reply_text(f"⚠️ Upload failed:\n{e}")

    # Optional cleanup
    try:
        os.remove(video_file)
    except Exception:
        pass


# ------------------- Run Bot -------------------
if __name__ == "__main__":
    print("🤖 Crunchyroll Bot Started...")
    app.run()
