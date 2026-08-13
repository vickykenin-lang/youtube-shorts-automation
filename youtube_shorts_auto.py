    def generate_audio(self, text, audio_path):
        """Generate TTS audio using gTTS."""
        try:
            tts = gTTS(text=text, lang='en')  # यदि हिंदी चाहिए तो 'en' की जगह 'hi' लिखें
            tts.save(audio_path)
            print(f"✅ Audio generated successfully: {audio_path}")
            return audio_path
        except Exception as e:
            print(f"❌ Error generating audio: {e}")
            return None
