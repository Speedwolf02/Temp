import os
import pytz
import asyncio
import ffmpeg
import subprocess
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from details import get_details, increment_episode, save_details

# ---------------- CONFIG ---------------- #
API_ID = 123456
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
UPLOAD_CHAT_ID = -1001234567890

DOWNLOAD_PATH = "./downloads"
AUDIO_PATH = "./audio"
MERGED_PATH = "./merged"
TIMEZONE = pytz.timezone("Asia/Kolkata")

bot = Client("auto_uploader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- UTILITIES ---------------- #
async def run_cmd(cmd: str):
    """Run shell command asynchronously."""
    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

def get_sorted_videos():
    """Return first 3 video files sorted by size (360p, 720p, 1080p)."""
    files = [os.path.join(DOWNLOAD_PATH, f) for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".mp4")]
    files.sort(key=lambda x: os.path.getsize(x))
    return files[:3]

async def merge_video_audio(video_path, audio_path, output_path):
    """Merge video + audio using ffmpeg."""
    (
        ffmpeg
        .input(video_path)
        .input(audio_path)
        .output(output_path, c="copy", loglevel="quiet")
        .run(overwrite_output=True)
    )

# ---------------- MAIN PROCESS ---------------- #
async def process_anime(title, video_dl_cmd, audio_dl_cmd):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    os.makedirs(AUDIO_PATH, exist_ok=True)
    os.makedirs(MERGED_PATH, exist_ok=True)

    now = datetime.now(TIMEZONE).strftime("%H:%M")
    print(f"[{now}] Starting task for {title}")

    # 1️⃣ Get season and episode info
    info = get_details(title)
    season, episode = info["season"], info["episode"]

    # 2️⃣ Run downloaders
    print("Downloading anime videos...")
    await run_cmd(video_dl_cmd)

    print("Downloading Crunchyroll audio...")
    await run_cmd(audio_dl_cmd)

    # 3️⃣ Get audio file
    audio_files = [os.path.join(AUDIO_PATH, f) for f in os.listdir(AUDIO_PATH) if f.endswith((".m4a", ".aac", ".mp3"))]
    if not audio_files:
        print("❌ No audio file found.")
        return
    audio_file = audio_files[0]

    # 4️⃣ Merge + Upload
    videos = get_sorted_videos()
    if not videos:
        print("❌ No video files found.")
        return

    for idx, vid in enumerate(videos, start=1):
        res = ["360p", "720p", "1080p"][idx - 1] if idx <= 3 else f"res{idx}"
        merged_file = os.path.join(MERGED_PATH, f"{title}_S{season:02d}E{episode:02d}_{res}.mp4")

        print(f"Merging {res} for {title} Ep {episode}...")
        await merge_video_audio(vid, audio_file, merged_file)

        print(f"Uploading {res}...")
        await bot.send_video(
            chat_id=UPLOAD_CHAT_ID,
            video=merged_file,
            caption=f"{title} S{season:02d}E{episode:02d} [{res}]",
            supports_streaming=True
        )

        os.remove(vid)
        os.remove(merged_file)

    os.remove(audio_file)

    # 5️⃣ Increment episode number for next week
    increment_episode(title)
    save_details()
    print(f"✅ Upload complete for {title} Ep {episode}. Next week: Ep {episode + 1}")

# ---------------- SCHEDULE ---------------- #
async def schedule_jobs():
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Solo Leveling - Wednesday 9 AM
    scheduler.add_job(
        lambda: asyncio.create_task(
            process_anime(
                "Solo Leveling",
                "python animepahe_dl.py --anime solo-leveling --latest",
                "python crunchy_audio_dl.py --anime solo-leveling"
            )
        ),
        trigger="cron",
        day_of_week="wed",
        hour=9,
        minute=0
    )

    # Naruto - Wednesday 10 PM
    scheduler.add_job(
        lambda: asyncio.create_task(
            process_anime(
                "Naruto",
                "python nx_downloader.py --anime naruto --latest",
                "python crunchy_audio_dl.py --anime naruto"
            )
        ),
        trigger="cron",
        day_of_week="wed",
        hour=22,
        minute=0
    )

    scheduler.start()
    print("✅ Scheduler started (Asia/Kolkata)")
    while True:
        await asyncio.sleep(60)

# ---------------- BOT ENTRY ---------------- #
@bot.on_message()
async def command_handler(_, message):
    if message.text == "/start":
        await message.reply("Auto Uploader Bot is Active ✅\n\nSchedules:\n🕘 Solo Leveling - Wed 9 AM\n🌙 Naruto - Wed 10 PM")

async def main():
    async with bot:
        await schedule_jobs()

if __name__ == "__main__":
    asyncio.run(main())
