"""
AIVA - AI Vocational Assistant
Flask Backend Server
"""
import os
import tempfile
import threading
import datetime
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
# Configuration
# ==============================================================================
API_KEY = os.environ.get("GROQ_API_KEY", "")
PDF_FOLDER_PATH = "data_files"
PORT = 5003

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
except:
    pass

# ==============================================================================
# Module Imports
# ==============================================================================
try:
    from pdf_ai_engine import PdfAIEngine
except ImportError:
    import glob
    import requests

    class PdfAIEngine:
        def __init__(self, pdf_folder_path, api_key):
            self.api_key = api_key
            self.knowledge_base = self._load_knowledge(pdf_folder_path)

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

app = Flask(__name__, static_folder='static', template_folder='templates')
ai = PdfAIEngine(pdf_folder_path=PDF_FOLDER_PATH, api_key=API_KEY)

state = {"last_question": "", "last_answer": ""}
state_lock = threading.Lock()

def update_state(key, value):
    with state_lock:
        state[key] = value

# ==============================================================================
# Routes
# ==============================================================================
@app.route("/")
def index():
    return render_template("aiva_portal.html")


@app.route("/ask", methods=["POST"])
def ask():
    """ถาม AI ด้วยข้อความ"""
    try:
        data = request.json
        text = data.get("question", "").strip()

        if not text:
            return jsonify({"ok": False, "answer": "No question"}), 400

        answer = ai.find_answer(text)
        update_state("last_question", text)
        update_state("last_answer", answer)

        return jsonify({"ok": True, "answer": answer})
    except Exception as e:
        return jsonify({"ok": False, "answer": str(e)}), 500


@app.route("/tts_audio", methods=["POST"])
def tts_audio():
    """สร้างไฟล์เสียงส่งให้ browser"""
    if not TTS_AVAILABLE:
        return jsonify({"ok": False, "error": "TTS not available"}), 500

    try:
        data = request.json
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"ok": False, "error": "No text"}), 400

        tts_obj = gTTS(text=text, lang='th', slow=False)
        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()
        tts_obj.save(tmp_path)

        return send_file(tmp_path, mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """บันทึกคะแนนดาว"""
    if not db:
        return jsonify({"success": True, "message": "ขอบคุณสำหรับคำแนะนำค่ะ"})

    try:
        data = request.get_json()
        rating = data.get('rating')
        feedback = data.get('feedback_text', '')

        db.collection('ratings').document().set({
            'rating': rating,
            'feedback': feedback,
            'timestamp': datetime.datetime.now(datetime.timezone.utc)
        })

        return jsonify({"success": True, "message": "ขอบคุณสำหรับคำแนะนำค่ะ"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# Main
# ==============================================================================
if __name__ == "__main__":
    print(f"AIVA Server running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
