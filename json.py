import json

# Store anime details in a Python dict
anime_data = {
    "Solo Leveling": {"season": 1, "episode": 7},
    "Naruto": {"season": 5, "episode": 188}
}

def get_details(anime_name: str):
    """Return season and episode for given anime."""
    return anime_data.get(anime_name, {"season": 1, "episode": 1})

def increment_episode(anime_name: str):
    """Increment episode number by +1."""
    if anime_name in anime_data:
        anime_data[anime_name]["episode"] += 1
    else:
        anime_data[anime_name] = {"season": 1, "episode": 2}

def save_details():
    """Optional — if you want to persist data, convert to JSON string."""
    with open("details.json", "w") as f:
        json.dump(anime_data, f, indent=4)
