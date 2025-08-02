import discord
from discord.ext import commands
import pytesseract
from PIL import Image
import aiohttp
import os
import re
from googleapiclient.discovery import build
from flask import Flask
import threading

# ======================
# CONFIG
# ======================
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)

# YouTube API client
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Regex to find base links in descriptions
BASE_LINK_REGEX = r"https:\/\/link\.clashofclans\.com\/[^\s]+"

# ======================
# SIMPLE WEB SERVER
# ======================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# ======================
# SLASH COMMAND
# ======================
@bot.tree.command(name="baselink", description="Upload a base screenshot to find the base link")
async def baselink(interaction: discord.Interaction, screenshot: discord.Attachment):
    await interaction.response.defer()

    # Download the screenshot
    file_path = f"/tmp/{screenshot.filename}"
    await screenshot.save(file_path)

    # OCR - extract text from image
    try:
        text = pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error reading image: {e}")
        return

    if not text.strip():
        await interaction.followup.send("⚠️ Could not read any text from the screenshot. Try a clearer image.")
        return

    # Use extracted text to search YouTube
    try:
        search_response = youtube.search().list(
            q=text,
            part="id,snippet",
            maxResults=5
        ).execute()

        base_link = None

        # Check video descriptions for base link
        for item in search_response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                video_id = item["id"]["videoId"]
                video_response = youtube.videos().list(
                    id=video_id,
                    part="snippet"
                ).execute()

                if video_response["items"]:
                    description = video_response["items"][0]["snippet"]["description"]
                    match = re.search(BASE_LINK_REGEX, description)
                    if match:
                        base_link = match.group(0)
                        break

        if base_link:
            await interaction.followup.send(f"✅ Found base link: {base_link}")
        else:
            await interaction.followup.send("❌ No base link found in top YouTube results. Try another image.")
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error searching YouTube: {e}")


# ======================
# START
# ======================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")


if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_TOKEN)
