# youtube_shorts_auto.py
import os
import json
import random
import asyncio
import requests
import datetime
import time
import base64
import pickle
from pathlib import Path
from dotenv import load_dotenv

# ---- Video & Audio ----
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
import edge_tts

# ---- Telegram ----
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ---- YouTube ----
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---- Scheduler ----
import schedule

# ---- ENV variables ----
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# YouTube OAuth token (base64 encoded) - will be decoded
TOKEN_B64 = os.getenv("YOUTUBE_TOKEN_B64")

# ---- Folders ----
Path("outputs").mkdir(exist_ok=True)
Path("downloads").mkdir(exist_ok=True)
Path("used_topics").mkdir(exist_ok=True)

# ============================================================
# 1. TOPICS GENERATOR (1050 topics)
# ============================================================
def generate_topics_file():
    if os.path.exists("topics.json"):
        return
    niches = {
        "motivation": ["5 habits of successful people", "how to stop overthinking", "morning routine of billionaires", "power of silence"],
        "finance": ["3 investing tips for beginners", "how to save ₹10000 per month", "credit card hacks", "mutual funds explained"],
        "health": ["how to lose belly fat fast", "benefits of drinking warm water", "morning yoga routine", "intermittent fasting guide"],
        "technology": ["AI tools for students", "best coding apps", "how to learn Python fast", "future of ChatGPT"],
        "facts": ["weird laws around the world", "scary ocean facts", "human body mysteries", "space secrets nasa hides"],
        "business": ["how to start a side hustle", "best business ideas 2026", "marketing psychology tricks", "how to negotiate salary"],
        "self_improvement": ["how to read 1 book a week", "memory improvement hacks", "public speaking tips", "how to make friends easily"],
        "gaming": ["free games 2026", "best mobile games", "gaming setup under 10000", "how to increase FPS"],
        "food": ["quick breakfast ideas", "street food recipes", "how to make perfect tea", "healthy snacks"],
        "travel": ["budget travel tips", "places to visit before 30", "how to travel solo", "best beaches in india"],
        "fashion": ["how to dress for your body type", "capsule wardrobe guide", "color combinations that work", "accessories to elevate look"],
        "education": ["how to study effectively", "best youtube channels for learning", "note taking methods", "how to score 95%"],
        "productivity": ["pomodoro technique", "how to automate your work", "best productivity apps", "deep work strategies"],
        "relationship": ["how to communicate better", "signs of a healthy relationship", "long distance tips", "how to make her feel special"],
        "science": ["quantum physics explained", "black holes demystified", "how vaccines work", "climate change facts"]
    }
    all_topics = []
    for niche, topics in niches.items():
        expanded = topics.copy()
        templates = ["best ", "how to ", "why ", "secrets of ", "tips for ", "benefits of "]
        for t in topics:
            for tmpl in templates[:2]:
                expanded.append(f"{tmpl}{t}")
        all_topics.extend([{"niche": niche, "topic": t} for t in expanded[:70]])
    random.shuffle(all_topics)
    with open("topics.json", "w", encoding="utf-8") as f:
        json.dump(all_topics[:1050], f, indent=2, ensure_ascii=False)
    print("✅ 1050+ topics generated")

# ============================================================
# 2. CORE CLASS
# ============================================================
class ShortsAutomation:
    def __init__(self):
        self.pexels_key = PEXELS_API_KEY
        self.tg_token = TELEGRAM_BOT_TOKEN
        self.tg_chat = TELEGRAM_CHAT_ID
        self.topics = []
        self.load_topics()
        # Load YouTube credentials from base64 if provided
        self.youtube_creds = None
        if TOKEN_B64:
            try:
                token_data = base64.b64decode(TOKEN_B64)
                self.youtube_creds = pickle.loads(token_data)
                print("✅ YouTube credentials loaded from secret.")
            except:
                pass
        # If no creds, we'll run OAuth flow (requires browser) - only for local testing

    def load_topics(self):
        if os.path.exists("topics.json"):
            with open("topics.json", "r") as f:
                self.topics = json.load(f)

    def get_used(self):
        used_file = "used_topics/used.txt"
        if os.path.exists(used_file):
            with open(used_file, "r") as f:
                return set(f.read().splitlines())
        return set()

    def mark_used(self, topic_id):
        with open("used_topics/used.txt", "a") as f:
            f.write(str(topic_id) + "\n")

    def get_next_topic(self):
        used = self.get_used()
        available = [t for t in self.topics if t['topic'] not in used]
        if not available:
            open("used_topics/used.txt", "w").close()
            available = self.topics
        chosen = random.choice(available)
        self.mark_used(chosen['topic'])
        return chosen['niche'], chosen['topic']

    def generate_script(self, niche, topic):
        hooks = ["🔥 Mind-blowing!", "⚠️ Most people don't know", "💰 This changed my life", "📈 The secret is", "💡 Watch till the end"]
        cta = ["Comment your thoughts!", "Share with a friend!", "Follow for more!"]
        return f"{random.choice(hooks)} {topic}. Here's why it matters. {random.choice(cta)}"

    async def generate_audio(self, text, path):
        voice = "en-IN-NeerjaNeural"
        comm = edge_tts.Communicate(text, voice)
        await comm.save(path)
        return path

    def download_bg(self, query, path):
        if not self.pexels_key:
            raise ValueError("❌ Pexels API key missing!")
        headers = {"Authorization": self.pexels_key}
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait"
        resp = requests.get(url, headers=headers)
        data = resp.json()
        videos = data.get('videos', [])
        if not videos:
            resp = requests.get("https://api.pexels.com/videos/search?query=nature&per_page=10&orientation=portrait", headers=headers)
            videos = resp.json().get('videos', [])
        if not videos:
            raise Exception("No videos found on Pexels")
        video = random.choice(videos)
        files = sorted(video['video_files'], key=lambda x: x.get('height', 0), reverse=True)
        hd = next((f for f in files if f['height'] >= 720), files[0])
        r = requests.get(hd['link'])
        with open(path, 'wb') as f:
            f.write(r.content)
        return path

    def render_shorts(self, audio_path, bg_path, text, output_path):
        audio = AudioFileClip(audio_path)
        duration = min(audio.duration, 58)
        bg = VideoFileClip(bg_path)
        bg = bg.resized(height=1920).with_duration(duration)
        txt = TextClip(
            text=text,
            font_size=50,
            color='white',
            stroke_color='black',
            stroke_width=2,
            font='Arial',
            method='caption',
            size=(bg.w * 0.9, None)
        ).with_position(('center', 0.75), relative=True).with_duration(duration)
        final = CompositeVideoClip([bg, txt]).with_audio(audio)
        final.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', threads=4)
        return output_path

    def quality_check(self, path):
        clip = VideoFileClip(path)
        checks = {
            "duration": 15 <= clip.duration <= 60,
            "size": os.path.getsize(path) < 45 * 1024 * 1024,
            "audio": clip.audio is not None and clip.audio.duration > 0
        }
        clip.close()
        return all(checks.values()), checks

    async def send_for_approval(self, video_path, niche, topic, script):
        if not self.tg_token or not self.tg_chat:
            print("⚠️ Telegram not set, auto-approving...")
            return "approve"
        bot = Bot(self.tg_token)
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("❌ Reject + Retry", callback_data="reject")
        ]]
        with open(video_path, 'rb') as f:
            msg = await bot.send_video(
                chat_id=self.tg_chat,
                video=f,
                caption=f"📹 *New Short Ready!*\n\n🏷️ *Niche:* {niche}\n📌 *Topic:* {topic}\n📝 *Script:* {script[:80]}...\n\nDecide:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return msg.message_id

    async def wait_for_decision(self, message_id, timeout=600):
        if not self.tg_token:
            return "approve"
        bot = Bot(self.tg_token)
        start = time.time()
        while time.time() - start < timeout:
            updates = await bot.get_updates()
            for up in updates:
                if up.callback_query and up.callback_query.message.message_id == message_id:
                    await up.callback_query.answer()
                    return up.callback_query.data
            await asyncio.sleep(5)
        print("⏰ Timeout! Auto-approving...")
        return "approve"

    def upload_youtube(self, video_path, topic, niche):
        # Use stored credentials if available
        creds = self.youtube_creds
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Fallback to OAuth flow (only works if browser available)
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secret.json",
                    scopes=["https://www.googleapis.com/auth/youtube.upload"]
                )
                creds = flow.run_local_server(port=0)
            # Save for future
            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)
        youtube = build("youtube", "v3", credentials=creds)
        now = datetime.datetime.now()
        target = now.replace(hour=7, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        if now >= target:
            target += datetime.timedelta(days=1)
        publish_time = target.isoformat() + "Z"
        body = {
            "snippet": {
                "title": f"{topic} #shorts",
                "description": f"Quick {niche} tip! 🚀\n\n{self.generate_script(niche, topic)}\n\n#shorts #{niche} #viral",
                "tags": [niche, "shorts", "viral"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "publishAt": publish_time
            }
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        print(f"✅ Uploaded! Video ID: {response['id']}, Scheduled for {publish_time}")
        return response

    async def run_once(self):
        print("\n🚀 Starting automation...")
        niche, topic = self.get_next_topic()
        print(f"📌 Topic: {topic} (Niche: {niche})")
        script = self.generate_script(niche, topic)
        print(f"📝 Script: {script}")
        audio_path = f"outputs/audio_{int(time.time())}.mp3"
        await self.generate_audio(script, audio_path)
        print("🔊 TTS generated.")
        bg_path = f"downloads/bg_{int(time.time())}.mp4"
        self.download_bg(topic, bg_path)
        print("🎬 Background downloaded.")
        vid_path = f"outputs/shorts_{int(time.time())}.mp4"
        self.render_shorts(audio_path, bg_path, script, vid_path)
        print("🎥 Video rendered.")
        ok, report = self.quality_check(vid_path)
        if not ok:
            print(f"⚠️ Quality failed: {report}. Retrying...")
            script = "🔥 " + script + " (Bonus tip!)"
            await self.generate_audio(script, audio_path)
            self.render_shorts(audio_path, bg_path, script, vid_path)
        msg_id = await self.send_for_approval(vid_path, niche, topic, script)
        decision = await self.wait_for_decision(msg_id)
        if decision == "approve":
            self.upload_youtube(vid_path, topic, niche)
        else:
            print("❌ Rejected. Regenerating...")
            script = "💡 " + script + " (New version)"
            await self.generate_audio(script, audio_path)
            self.download_bg("cinematic", bg_path)
            self.render_shorts(audio_path, bg_path, script, vid_path)
            print("🔄 Auto-uploading retry version...")
            self.upload_youtube(vid_path, topic, niche)

def main():
    print("="*50)
    print("🤖 YOUTUBE SHORTS AUTOMATOR (GitHub Actions)")
    print("="*50)
    generate_topics_file()
    # If running on GitHub Actions, we just run once
    auto = ShortsAutomation()
    asyncio.run(auto.run_once())

if __name__ == "__main__":
    main()
