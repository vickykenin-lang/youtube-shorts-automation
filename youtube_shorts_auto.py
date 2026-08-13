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
# --- Video & Audio --- |
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
from gtts import gTTS  # <--- यहाँ edge_tts की जगह gtts डाला है
# --- Telegram ---
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
# --- Youtube ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
