import os
import pytz
import ffmpeg
import asyncio
import subprocess
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from details import get_details, increment_episode
from anime_utils import get_anime_data

# ---------------- CONFIG ---------------- #
API_ID = 123456
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"

UPLOAD_CHAT_ID = -1001234567890     # main upload channel
DATABASE_CHAT_ID = -1009876543210   # database channel (for file storage)

DOWNLOAD_PATH = "./downloads"
AUDIO_PATH = "./audio"
MERGED_PATH = "./merged"
TIMEZONE = pytz.timezone("Asia/Kolkata")

bot = Client("auto_uploader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Track ongoing uploads
episode_post_map = {}  # { "AnimeName": {"episode": int, "message_id": int, "buttons": []} }

# ---------------- UTILITIES ---------------- #
async def run_cmd(cmd: str):
    process = await asyncio.create_subprocess_shell(cmd)
    await process.communicate()

def get_sorted_videos():
    files = [os.path.join(DOWNLOAD_PATH, f) for f in os.listdir(DOWNLOAD_PATH) if f.endswith(".mp4")]
    files.sort(key=lambda x: os.path.getsize(x))
    return files[:3]

async def merge(video, audio, output):
    ffmpeg.input(video).input(audio).output(output, c="copy", loglevel="quiet").run(overwrite_output=True)

# ---------------- CORE FUNCTION ---------------- #
async def process_anime(title, video_dl_cmd, audio_dl_cmd):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    os.makedirs(AUDIO_PATH, exist_ok=True)
    os.makedirs(MERGED_PATH, exist_ok=True)

    info = get_details(title)
    season, episode = info["season"], info["episode"]

    ani = get_anime_data(title)
    caption = (
        f"🎬 **{ani['title']}**\n"
        f"📺 Season {season} • Episode {episode}\n"
        f"🗓 {ani['season']} {ani['year']}\n\n"
        f"{ani['desc']}..."
    )

    # STEP 1: Post cover with caption first
    post = await bot.send_photo(
        chat_id=UPLOAD_CHAT_ID,
        photo=ani["image"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏳ Processing...", callback_data="wait")]])
    )

    # Store in map for later editing
    episode_post_map[title] = {
        "episode": episode,
        "message_id": post.id,
        "buttons": []
    }

    print(f"[{datetime.now(TIMEZONE).strftime('%H:%M')}] Posted {title} Ep {episode}, starting downloads...")

    # STEP 2: Download video & audio
    await run_cmd(video_dl_cmd)
    await run_cmd(audio_dl_cmd)

    audio_files = [os.path.join(AUDIO_PATH, f) for f in os.listdir(AUDIO_PATH) if f.endswith((".m4a", ".aac", ".mp3"))]
    if not audio_files:
        print("❌ No audio found.")
        return
    audio_file = audio_files[0]

    videos = get_sorted_videos()
    qualities = ["480p", "720p", "1080p"]

    for idx, vid in enumerate(videos):
        res = qualities[idx]
        merged_file = os.path.join(MERGED_PATH, f"{title}_S{season:02d}E{episode:02d}_{res}.mp4")

        print(f"Merging {res} for {title} Ep {episode}...")
        await merge(vid, audio_file, merged_file)

        # Upload to DB channel
        print(f"Uploading {res} to DB...")
        db_msg = await bot.send_video(
            chat_id=DATABASE_CHAT_ID,
            video=merged_file,
            caption=f"{title} S{season:02d}E{episode:02d} [{res}]",
            supports_streaming=True
        )

        # Create download link
        link = f"https://t.me/c/{str(db_msg.chat.id)[4:]}/{db_msg.id}"

        # Add new button
        episode_post_map[title]["buttons"].append(
            [InlineKeyboardButton(f"{res}", url=link)]
        )

        # Update the same post buttons dynamically
        await bot.edit_message_reply_markup(
            chat_id=UPLOAD_CHAT_ID,
            message_id=episode_post_map[title]["message_id"],
            reply_markup=InlineKeyboardMarkup(episode_post_map[title]["buttons"])
        )

        os.remove(vid)
        os.remove(merged_file)

        # If 3 qualities done → cleanup
        if len(episode_post_map[title]["buttons"]) == 3:
            del episode_post_map[title]
            increment_episode(title)
            os.remove(audio_file)
            print(f"✅ {title} Ep {episode} complete! All 3 qualities uploaded.")
            break

# ---------------- SCHEDULE JOBS ---------------- #
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
        trigger="cron", day_of_week="wed", hour=9, minute=0
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
        trigger="cron", day_of_week="wed", hour=22, minute=0
    )

    scheduler.start()
    print("✅ Scheduler started (Asia/Kolkata)")
    while True:
        await asyncio.sleep(60)

# ---------------- BOT START ---------------- #
@bot.on_message()
async def start(_, msg):
    if msg.text == "/start":
        await msg.reply("🚀 Auto Anime Bot Running!\n\n🕘 Solo Leveling - Wed 9 AM\n🌙 Naruto - Wed 10 PM")

async def main():
    async with bot:
        await schedule_jobs()

if __name__ == "__main__":
    asyncio.run(main())
