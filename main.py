import discord
from discord.ext import commands
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
OCR_API_KEY = os.getenv("OCR_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)

# YouTube API client
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Regex to find base links in descriptions
BASE_LINK_REGEX = r"https:\/\/link\.clashofclans\.com\/[^\s]+"

# ======================
# SIMPLE WEB SERVER (for Render free)
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
# OCR FUNCTION (OCR.space)
# ======================
async def extract_text_from_image(image_path):
    async with aiohttp.ClientSession() as session:
        with open(image_path, 'rb') as image_file:
            form = aiohttp.FormData()
            form.add_field('apikey', OCR_API_KEY)
            form.add_field('file', image_file, filename=image_path)
            form.add_field('language', 'eng')

            async with session.post('https://api.ocr.space/parse/image', data=form) as resp:
                result = await resp.json()
                if result.get("IsErroredOnProcessing", True):
                    return ""
                return result["ParsedResults"][0]["ParsedText"]

# ======================
# SLASH COMMAND
# ======================
@bot.tree.command(name="baselink", description="Upload a base screenshot to find the base link")
async def baselink(interaction: discord.Interaction, screenshot: discord.Attachment):
    await interaction.response.defer()

    # Download the screenshot
    file_path = f"/tmp/{screenshot.filename}"
    await screenshot.save(file_path)

    # OCR - extract text from image using OCR.space
    text = await extract_text_from_image(file_path)
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
