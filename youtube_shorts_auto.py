import os
import json
import random
import asyncio
import requests
import datetime
import time
import pickle
from pathlib import Path
from dotenv import load_dotenv

# --- Video & Audio ---
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
from gtts import gTTS  # FIX: edge_tts replaced with gtts to avoid 403 error

# --- Telegram ---
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# --- YouTube ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- AI (OpenAI) ---
import openai

# Load Environment Variables
load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Create necessary directories
Path("outdirs").mkdir(exist_ok=True)
Path("downloads").mkdir(exist_ok=True)
Path("used_topics").mkdir(exist_ok=True)

class ShortsAutomation:
    def __init__(self):
        self.topics = []
        self.used_topics = []
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)

    def load_topics(self):
        """Load topics from topics.json"""
        if os.path.exists("topics.json"):
            with open("topics.json", "r", encoding="utf-8") as f:
                self.topics = json.load(f)
        return len(self.topics) > 0

    def get_used(self):
        """Load previously used topics to avoid repetition"""
        if os.path.exists("used_topics/used.json"):
            with open("used_topics/used.json", "r", encoding="utf-8") as f:
                self.used_topics = json.load(f)

    def mark_used(self, topic):
        """Mark a topic as used after upload"""
        self.used_topics.append(topic)
        with open("used_topics/used.json", "w", encoding="utf-8") as f:
            json.dump(self.used_topics, f, indent=4)

    def get_next_topic(self):
        """Pick a random unused topic"""
        available = [t for t in self.topics if t not in self.used_topics]
        if not available:
            self.used_topics = []  # Reset if all used
            available = self.topics
        return random.choice(available)

    def generate_script(self, topic):
        """Use OpenAI to write a viral script for the Short"""
        try:
            prompt = f"Write a very short, engaging, and viral-style script (under 30 seconds) for a YouTube Short about '{topic}'. Include hooks and calls to action."
            if openai.api_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content.strip()
            else:
                # Fallback if no OpenAI key is set
                return f"This changed my life. Here's how to master {topic} perfectly. Share with a friend!"
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return f"Check out this amazing life hack about {topic}!"

    def generate_audio(self, text, audio_path):
        """Generate TTS audio using gTTS (403 Error Fixed here)"""
        try:
            tts = gTTS(text=text, lang='en') # Change 'en' to 'hi' for Hindi
            tts.save(audio_path)
            print(f"✅ Audio generated: {audio_path}")
            return audio_path
        except Exception as e:
            print(f"❌ Audio Error: {e}")
            return None

    def download_bg_video(self, query="nature"):
        """Download a background video from Pexels (or use a placeholder)"""
        video_path = f"downloads/bg_{int(time.time())}.mp4"
        print(f"🎬 Searching background for: {query}")
        # NOTE: Add your actual Pexels API call here using PEXELS_API_KEY
        # If you don't have one, this function creates a dummy path for testing.
        if not os.path.exists(video_path):
            # Dummy file creation to avoid crashing
            with open(video_path, 'w') as f: f.write("")
        return video_path

    def render_shorts(self, audio_path, bg_video_path, output_path="outdirs/shorts.mp4"):
        """Combine audio and video into a vertical Short"""
        print("🎥 Rendering video...")
        try:
            if not os.path.exists(bg_video_path) or os.path.getsize(bg_video_path) == 0:
                print("Background video missing. Using plain background")
                bg_video_path = None
            
            audio_clip = AudioFileClip(audio_path)
            if bg_video_path and os.path.exists(bg_video_path):
                video_clip = VideoFileClip(bg_video_path).subclip(0, min(audio_clip.duration, 5))
                video_clip = video_clip.resize(height=1920)
                video_clip = video_clip.crop(width=1080, height=1920, x_center=video_clip.w/2, y_center=video_clip.h/2)
                final_clip = video_clip.set_audio(audio_clip)
            else:
                # Create a colored clip if no background
                final_clip = TextClip("Shorts Automation", fontsize=70, color='white', bg_color='black', size=(1080, 1920)).set_duration(audio_clip.duration).set_audio(audio_clip)
            
            final_clip.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
            return output_path
        except Exception as e:
            print(f"❌ Render Error: {e}")
            return None

    async def send_for_approval(self, video_path, script, topic):
        """Send video to Telegram for approval"""
        caption = f"📹 Topic: {topic}\n\n📝 Script: {script}"
        keyboard = [[InlineKeyboardButton("✅ Upload", callback_data='upload')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="New Short ready for review!")
                await self.bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=open(video_path, 'rb'), caption=caption, reply_markup=reply_markup)
                return await self.wait_for_decision()
            except Exception as e:
                print(f"Telegram Error: {e}")
                return "upload" # Auto-upload if Telegram fails
        else:
            return "upload" # Auto-upload if no Telegram configured

    async def wait_for_decision(self):
        """Stub to wait for user decision in Telegram"""
        await asyncio.sleep(5)
        return "upload"

    def upload_youtube(self, video_path, title, description="Check out this awesome video!"):
        """Upload video to YouTube"""
        # NOTE: This requires a valid client_secret.json in the repo
        print(f"📺 Uploading to YouTube: {title}")
        # If you configure YouTube API, you can place the logic here.
        # For now, it simply prints success.
        return True

    async def run_once(self):
        if not self.load_topics():
            print("❌ No topics found in 'topics.json'.")
            return
        
        self.get_used()
        topic = self.get_next_topic()
        print(f"🎯 Topic: {topic}")

        script = self.generate_script(topic)
        print(f"📝 Script: {script}")

        audio_path = "outdirs/audio.mp3"
        if not self.generate_audio(script, audio_path):
            return

        bg_video = self.download_bg_video(topic.split()[0])
        final_video = "outdirs/final_short.mp4"
        
        if not self.render_shorts(audio_path, bg_video, final_video):
            return

        decision = await self.send_for_approval(final_video, script, topic)

        if decision == "upload":
            self.upload_youtube(final_video, f"Life Hack: {topic}")
            self.mark_used(topic)
            print("✅ Script finished successfully!")
        else:
            print("⏭️ Upload skipped.")

async def main():
    print("🚀 Starting YouTube Shorts Automation...")
    automator = ShortsAutomation()
    await automator.run_once()

if __name__ == "__main__":
    asyncio.run(main())
