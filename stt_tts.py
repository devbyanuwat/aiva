import speech_recognition as sr
from gtts import gTTS
import threading
import os
import tempfile
import pygame
import time

# --- Setup Pygame Mixer ---
try:
    # ตั้งค่า Mixer ควรทำเพียงครั้งเดียว
    pygame.mixer.init()
    print("Pygame Mixer initialized successfully.")
except pygame.error as e:
    print(f"Warning: Pygame Mixer could not be initialized. Audio might fail. Error: {e}")

# ----------------------------------------------

class STT:
    def __init__(self, language='th-TH'):
        self.recognizer = sr.Recognizer()
        self.language = language

    def listen_from_mic(self, timeout=5, phrase_time_limit=7):
        with sr.Microphone() as source:
            print("ปรับเสียงพื้นหลัง... (กรุณารอ)")
            # self.recognizer.energy_threshold = 400 
            self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
            print("ฟังคำถาม...")
            
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                print("STT timeout: ไม่ได้ยินเสียงภายในเวลาที่กำหนด")
                return ""

        try:
            text = self.recognizer.recognize_google(audio, language=self.language, show_all=False)
            print("ข้อความที่ได้:", text)
            return text
        except sr.UnknownValueError:
            print("STT unknown value: ไม่สามารถเข้าใจคำพูด")
            return ""
        except sr.RequestError as e:
            print("STT request failed:", e)
            return ""

class TTS:
    def __init__(self, lang='th'):
        self.lang = lang
        self.lock = threading.Lock()
        self.current_path = None
        self.is_speaking = False

    def speak(self, text):
        # ⭐️ ตรวจสอบว่า mixer พร้อมทำงานหรือไม่ ถ้าไม่ ให้ init ใหม่
        if not pygame.mixer.get_init():
            print("TTS: Mixer not initialized, attempting to re-init...")
            try:
                pygame.mixer.init()
                print("TTS: Mixer re-initialized successfully.")
            except pygame.error as e:
                print(f"TTS Error: Could not re-initialize mixer: {e}")
                return

        path = None
        try:
            self.is_speaking = True
            print(f"TTS: Generating speech for: {text[:30]}...")
            
            # 1. สร้างไฟล์เสียง
            with self.lock:
                # ⭐️⭐️⭐️ แก้ไขตรงนี้: เพิ่ม slow=False เพื่อเพิ่มความเร็วในการพูด ⭐️⭐️⭐️
                tts = gTTS(text=text, lang=self.lang, slow=False) 
                # ⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                    path = tmp_file.name
                tts.save(path)
                self.current_path = path
            
            # 2. เล่นเสียงด้วย pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                
                # 3. รอจนกว่าจะเล่นจบ
                while pygame.mixer.music.get_busy() and self.is_speaking:
                    time.sleep(0.1)
                
                # สั่ง Unload ไฟล์ก่อนลบ (ถ้ายังไม่ถูกหยุด)
                if self.is_speaking: # ถ้าเล่นจนจบเอง (ไม่ถูก stop)
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            else:
                print("TTS Error: Pygame Mixer not initialized.")
            
        except Exception as e:
            print(f"TTS speak error: {e}")
        finally:
            self.is_speaking = False
            
            # 4. ลบไฟล์ (cleanup)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    # print(f"TTS cleanup: Removed {os.path.basename(path)}")
                except Exception as e:
                    # อาจจะยัง Unload ไม่เสร็จ
                    print(f"TTS cleanup error: Could not remove {path}. {e}")
            self.current_path = None

    def stop_speaking(self):
        """เมธอดสำหรับสั่งหยุดการพูดทันที"""
        if self.is_speaking and pygame.mixer.get_init():
            print("TTS: Stop command received. Stopping playback.")
            self.is_speaking = False # ⭐️ ตั้งค่าสถานะก่อน
            pygame.mixer.music.stop()
            pygame.mixer.music.unload() # ⭐️ สั่ง unload ทันที
        elif not pygame.mixer.get_init():
            print("TTS: Stop command received, but mixer is not running.")