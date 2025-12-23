"""
AIVA - AI Vocational Assistant
Flask Backend Server
"""
import os
import tempfile
import threading
import datetime
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, jsonify, request, send_file

# ==============================================================================
# Load .env file
# ==============================================================================
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# ==============================================================================
# Logging Configuration
# ==============================================================================
def setup_logging():
    """ตั้งค่าระบบ logging แบบหมุนเวียนไฟล์อัตโนมัติ"""
    # สร้างโฟลเดอร์ logs ถ้ายังไม่มี
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # สร้าง RotatingFileHandler (หมุนเวียนเมื่อไฟล์ใหญ่ถึง 10MB, เก็บไว้ 5 ไฟล์)
    log_file = os.path.join(log_dir, "aiva.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )

    # กำหนด format สำหรับ log (plain text)
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(log_format)

    # สร้าง console handler สำหรับแสดงผลใน terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)

    # ตั้งค่า root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # จับทุก level
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return logging.getLogger(__name__)

logger = setup_logging()
logger.info("=" * 60)
logger.info("AIVA System Starting Up")
logger.info("=" * 60)

# ==============================================================================
# Configuration
# ==============================================================================
API_KEY = os.environ.get("GROQ_API_KEY", "")
PDF_FOLDER_PATH = "data_files"
PORT = 5003

logger.info(f"Configuration loaded - PDF Folder: {PDF_FOLDER_PATH}, Port: {PORT}")

# ==============================================================================
# Firebase Setup
# ==============================================================================
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase connected successfully")
    else:
        logger.warning("Firebase serviceAccountKey.json not found - feedback storage disabled")
except Exception as e:
    logger.error(f"Firebase initialization error: {e}")
    pass

# ==============================================================================
# Module Imports
# ==============================================================================
try:
    from pdf_ai_engine import PdfAIEngine
except ImportError:
    import glob
    import requests
    import json

    class PdfAIEngine:
        def __init__(self, pdf_folder_path, api_key):
            self.api_key = api_key
            self.knowledge_base = self._load_knowledge(pdf_folder_path)
            self.faq_data = self._load_faq()

        def _load_knowledge(self, folder_path):
            """อ่านข้อมูลจาก PDF และ TXT"""
            all_text = ""

            # อ่าน TXT files
            for txt_path in glob.glob(os.path.join(folder_path, '*.txt')):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        all_text += f.read() + "\n"
                except:
                    pass

            # อ่าน PDF files (ถ้ามี pdfplumber)
            try:
                import pdfplumber
                for pdf_path in glob.glob(os.path.join(folder_path, '*.pdf')):
                    try:
                        with pdfplumber.open(pdf_path) as pdf:
                            for page in pdf.pages:
                                t = page.extract_text()
                                if t:
                                    all_text += t + "\n"
                    except:
                        pass
            except ImportError:
                pass

            return all_text if all_text else "ไม่มีข้อมูล"

        def _load_faq(self):
            """โหลดข้อมูล FAQ จากไฟล์ faq.json"""
            try:
                if os.path.exists('faq.json'):
                    with open('faq.json', 'r', encoding='utf-8') as f:
                        return json.load(f)
            except:
                pass
            return []

        def _check_faq(self, question):
            """ตรวจสอบว่าคำถามตรงกับ FAQ หรือไม่"""
            question_lower = question.lower().strip()
            for faq in self.faq_data:
                keywords = faq.get("keywords", [])
                for keyword in keywords:
                    if keyword.lower() in question_lower:
                        return faq.get("answer", "")
            return None

        def _get_context(self, question, max_chars=6000):
            """เลือกข้อมูลที่เกี่ยวข้อง"""
            if len(self.knowledge_base) < max_chars:
                return self.knowledge_base

            chunks = [self.knowledge_base[i:i+1000] for i in range(0, len(self.knowledge_base), 1000)]
            scored = []
            for i, chunk in enumerate(chunks):
                score = sum(1 for k in question.split() if len(k) > 2 and k in chunk)
                scored.append((score, i, chunk))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = sorted(scored[:8], key=lambda x: x[1])
            return "\n".join([c[2] for c in top])

        def find_answer(self, question):
            """ถาม AI ผ่าน Groq API"""
            # ตรวจสอบ FAQ ก่อน
            faq_answer = self._check_faq(question)
            if faq_answer:
                return faq_answer

            context = self._get_context(question)

            prompt = f"""บทบาท: คุณคือเจ้าหน้าที่ประชาสัมพันธ์หญิง พูดจาสุภาพ เป็นมิตร กระชับ
คำสั่ง: ตอบสั้นๆ 3-5 บรรทัด ไม่ใช้ Markdown ไม่พูดว่า "ไม่มีในเอกสาร"

[ข้อมูล]
{context}

คำถาม: {question}
คำตอบ:"""

            models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]

            for model in models:
                try:
                    res = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.5,
                            "max_tokens": 400
                        },
                        timeout=30
                    )

                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"].strip()
                    elif res.status_code == 429:
                        continue
                    else:
                        return "ขออภัย ระบบขัดข้อง"
                except:
                    continue

            return "ขออภัย ระบบมีผู้ใช้งานมาก กรุณาลองใหม่"

try:
    from gtts import gTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ==============================================================================
# Flask App Setup
# ==============================================================================
os.makedirs(PDF_FOLDER_PATH, exist_ok=True)
logger.info(f"PDF folder created/verified: {PDF_FOLDER_PATH}")

app = Flask(__name__, static_folder='static', template_folder='templates')
logger.info("Flask app initialized")

ai = PdfAIEngine(pdf_folder_path=PDF_FOLDER_PATH, api_key=API_KEY)
logger.info("AI Engine initialized")

state = {"last_question": "", "last_answer": ""}
state_lock = threading.Lock()

def update_state(key, value):
    with state_lock:
        state[key] = value
        logger.debug(f"State updated: {key} = {value[:50] if isinstance(value, str) else value}...")

# ==============================================================================
# Routes
# ==============================================================================
@app.route("/")
def index():
    logger.info(f"Request: GET / from {request.remote_addr}")
    return render_template("aiva_portal.html")


@app.route("/greeting", methods=["GET"])
def greeting():
    """ส่งข้อความทักทายเริ่มต้น"""
    logger.info(f"Request: GET /greeting from {request.remote_addr}")
    greetings = [
        "สวัสดีค่ะ! ดิฉันชื่อไอว่า ยินดีต้อนรับเข้าสู่ระบบค่ะ มีอะไรให้ช่วยไหมคะ",
        "สวัสดีค่ะ! ดิฉันไอว่า ผู้ช่วยอัจฉริยะของวิทยาลัยพณิชยการธนบุรี ยินดีให้บริการค่ะ",
        "สวัสดีค่ะ! ดิฉันไอว่าค่ะ มีคำถามอะไรเกี่ยวกับการรับสมัคร หลักสูตร หรืออาชีพ สอบถามได้เลยนะคะ"
    ]
    import random
    message = random.choice(greetings)
    logger.info(f"Response: /greeting - Sent greeting message")
    return jsonify({"ok": True, "message": message})


@app.route("/ask", methods=["POST"])
def ask():
    """ถาม AI ด้วยข้อความ"""
    try:
        data = request.json
        text = data.get("question", "").strip()
        logger.info(f"Request: POST /ask from {request.remote_addr}")
        logger.info(f"Question received: {text}")

        if not text:
            logger.warning("Empty question received")
            return jsonify({"ok": False, "answer": "No question"}), 400

        logger.debug(f"Sending question to AI engine: {text}")
        answer = ai.find_answer(text)
        logger.info(f"AI Response: {answer[:100]}...")

        update_state("last_question", text)
        update_state("last_answer", answer)

        return jsonify({"ok": True, "answer": answer})
    except Exception as e:
        logger.error(f"Error in /ask endpoint: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "answer": str(e)}), 500


@app.route("/tts_audio", methods=["POST"])
def tts_audio():
    """สร้างไฟล์เสียงส่งให้ browser"""
    logger.info(f"Request: POST /tts_audio from {request.remote_addr}")

    if not TTS_AVAILABLE:
        logger.warning("TTS requested but not available")
        return jsonify({"ok": False, "error": "TTS not available"}), 500

    try:
        data = request.json
        text = data.get("text", "").strip()
        logger.debug(f"TTS text: {text[:50]}...")

        if not text:
            logger.warning("Empty TTS text received")
            return jsonify({"ok": False, "error": "No text"}), 400

        logger.info("Generating TTS audio...")
        tts_obj = gTTS(text=text, lang='th', slow=False)
        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()
        tts_obj.save(tmp_path)
        logger.info(f"TTS audio generated: {tmp_path}")

        return send_file(tmp_path, mimetype='audio/mpeg')
    except Exception as e:
        logger.error(f"Error in /tts_audio endpoint: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """บันทึกคะแนนดาว"""
    logger.info(f"Request: POST /submit_feedback from {request.remote_addr}")

    if not db:
        logger.warning("Feedback received but Firebase not configured")
        return jsonify({"success": True, "message": "ขอบคุณสำหรับคำแนะนำค่ะ"})

    try:
        data = request.get_json()
        rating = data.get('rating')
        feedback = data.get('feedback_text', '')
        logger.info(f"Feedback received - Rating: {rating}, Text: {feedback[:50] if feedback else 'N/A'}...")

        db.collection('ratings').document().set({
            'rating': rating,
            'feedback': feedback,
            'timestamp': datetime.datetime.now(datetime.timezone.utc)
        })
        logger.info("Feedback saved to Firebase successfully")

        return jsonify({"success": True, "message": "ขอบคุณสำหรับคำแนะนำค่ะ"})
    except Exception as e:
        logger.error(f"Error in /submit_feedback endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# Main
# ==============================================================================
if __name__ == "__main__":
    logger.info(f"Starting AIVA Server on port {PORT}")
    logger.info("Server is ready to accept connections")
    try:
        app.run(host="0.0.0.0", port=PORT, debug=False)
    except Exception as e:
        logger.critical(f"Server crashed: {str(e)}", exc_info=True)
        raise
