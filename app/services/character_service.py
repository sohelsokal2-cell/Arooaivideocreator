import os
import urllib.parse
from pathlib import Path
import aiohttp
from app.config import DEFAULT_CHARACTER_PATH, CHARACTERS_DIR

async def get_or_create_character(character_prompt: str = None, job_id: str = "temp") -> Path:
    """
    Returns the character image path.
    If character_prompt is None or 'default', returns default stand-up comedian asset.
    Otherwise, generates a high-res stand-up comedian image using Pollinations AI (100% Free, 0 GPU).
    """
    if not character_prompt or character_prompt.lower() in ["default", "standup_girl", "standard"]:
        if DEFAULT_CHARACTER_PATH.exists():
            return DEFAULT_CHARACTER_PATH

    # Dynamic generation via free cloud image engine
    clean_prompt = character_prompt if character_prompt and character_prompt.lower() != "auto" else "young expressive stand-up comedian holding a microphone on comedy club stage with warm spotlight, dark background, photorealistic 8k vertical portrait"
    encoded_prompt = urllib.parse.quote(clean_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&seed=42"

    dest_path = CHARACTERS_DIR / f"{job_id}_char.png"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(dest_path, "wb") as f:
                        f.write(content)
                    return dest_path
    except Exception as e:
        print(f"Error generating dynamic character: {e}, falling back to default.")

    return DEFAULT_CHARACTER_PATH

