import os
import re
import aiohttp
import anitopy
from io import BytesIO
from PIL import Image
from datetime import datetime
from typing import Optional, Tuple
from pyrogram.types import InputMediaPhoto

# ──────────────── AniList GraphQL Query ──────────────── #
ANIME_GRAPHQL_QUERY = """
query ($search: String, $seasonYear: Int) {
  Media(search: $search, seasonYear: $seasonYear, type: ANIME) {
    id
    title {
      english
      romaji
      native
    }
    description
    episodes
    genres
    seasonYear
    coverImage {
      extraLarge
      large
      medium
      color
    }
  }
}
"""

# ──────────────── Extract Season & Episode ──────────────── #
def extract_season_episode(filename: str) -> Tuple[Optional[str], Optional[str]]:
    patterns = [
        re.compile(r'[Ss](\d+)[\s\-]*[Ee]?[Pp]?(\d+)'),
        re.compile(r'[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)', re.IGNORECASE),
        re.compile(r'\[[Ss](\d+)\]\[[Ee]?[Pp]?(\d+)\]', re.IGNORECASE),
        re.compile(r'(\d+)[xX](\d+)'),
        re.compile(r'\b[Ee][Pp]?\s*(\d+)\b')
    ]
    for p in patterns:
        match = p.search(filename)
        if match:
            season = match.group(1)
            episode = match.group(2) if len(match.groups()) > 1 else None
            return season, episode
    return None, None


# ──────────────── AniList Fetcher ──────────────── #
async def fetch_anilist_data(anime_name: str, year: int = datetime.now().year) -> dict:
    url = "https://graphql.anilist.co"
    variables = {"search": anime_name, "seasonYear": year}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": ANIME_GRAPHQL_QUERY, "variables": variables}) as resp:
            data = await resp.json()
            return data.get("data", {}).get("Media", {}) or {}


# ──────────────── Thumbnail Converter ──────────────── #
async def make_thumbnail_from_url(image_url: str, size: Tuple[int, int] = (320, 320)) -> BytesIO:
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            img_data = await resp.read()

    image = Image.open(BytesIO(img_data))
    image.thumbnail(size)
    thumb_io = BytesIO()
    image.save(thumb_io, format="JPEG")
    thumb_io.seek(0)
    return thumb_io


# ──────────────── Main Function ──────────────── #
async def get_anime_info(filename: str):
    """Extracts anime details, gets AniList data, creates thumbnail and returns all info."""
    
    # Step 1: Extract data from filename
    parsed = anitopy.parse(filename)
    anime_name = parsed.get("anime_title") or os.path.splitext(filename)[0]
    season, episode = extract_season_episode(filename)
    if not season:
        season = parsed.get("anime_season") or "1"
    if not episode:
        episode = parsed.get("episode_number") or "1"

    # Step 2: Fetch AniList data
    ani_data = await fetch_anilist_data(anime_name)
    if not ani_data:
        return None

    title = ani_data["title"].get("english") or ani_data["title"].get("romaji") or ani_data["title"].get("native")
    desc = re.sub(r"<.*?>", "", ani_data.get("description", ""))[:700]
    genres = ", ".join(ani_data.get("genres", []))
    poster_url = ani_data["coverImage"]["large"]
    total_eps = ani_data.get("episodes", "??")
    year = ani_data.get("seasonYear", "??")

    # Step 3: Make thumbnail
    thumb_io = await make_thumbnail_from_url(poster_url)

    # Step 4: Prepare caption for upload
    caption = (
        f"🎬 **{title}** ({year})\n"
        f"📺 Season: {season} | Episode: {episode}/{total_eps}\n"
        f"🎭 Genres: {genres}\n\n"
        f"📝 {desc}\n"
        f"———\n"
        f"@AnimeUploaderBot"
    )

    # Step 5: Return structured data
    return {
        "title": title,
        "anime_name": anime_name,
        "season": season,
        "episode": episode,
        "poster_url": poster_url,
        "thumb_io": thumb_io,
        "caption": caption
    }


# ──────────────── Pyrogram Example Usage ──────────────── #
"""
from pyrogram import Client

app = Client("uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.document | filters.video)
async def upload_anime(_, message):
    file_name = message.document.file_name if message.document else message.video.file_name
    info = await get_anime_info(file_name)
    if not info:
        await message.reply("❌ Couldn't fetch AniList data.")
        return
    
    # Upload with thumbnail and caption
    await message.reply_photo(
        photo=InputMediaPhoto(info['thumb_io']),
        caption=info['caption']
    )

app.run()
"""
