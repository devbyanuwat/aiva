# AIVA - AI Vocational Assistant

ผู้ช่วยอัจฉริยะเพื่อสังคมอาชีวะแห่งอนาคต

## Features

- ถาม-ตอบด้วยเสียง (Speech Recognition)
- Text-to-Speech ภาษาไทย
- AI ตอบคำถามจากฐานข้อมูล PDF/TXT
- ระบบประเมินความพึงพอใจ

## Requirements

- Python 3.8+
- Chrome/Edge Browser (สำหรับ Speech Recognition)

## Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/AIVA.git
cd AIVA

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. สร้างไฟล์ `.env` จาก `.env.example`:
```bash
cp .env.example .env
```

2. ใส่ Groq API Key ใน `.env`:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxx
```
   Get API Key: https://console.groq.com/keys

3. ใส่ข้อมูลใน `data_files/`:
   - ไฟล์ `.pdf` หรือ `.txt`

4. (Optional) Firebase - ใส่ `serviceAccountKey.json`

## Usage

### Development
```bash
# Mac/Linux
./run_aiva.sh

# Windows
run_aiva.bat
```

### Production
```bash
./run_aiva.sh --production
```

เปิด Browser ไปที่ `http://localhost:5002`

## Project Structure

```
AIVA/
├── app.py              # Flask Server
├── pdf_ai_engine.py    # AI Engine
├── stt_tts.py          # Speech modules
├── templates/
│   └── aiva_portal.html
├── static/
│   ├── logo01.png
│   └── aivavideo.mp4
├── data_files/         # Knowledge base (PDF/TXT)
├── requirements.txt
├── run_aiva.sh         # Mac/Linux launcher
└── run_aiva.bat        # Windows launcher
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | หน้าเว็บหลัก |
| `/ask` | POST | ถาม AI |
| `/tts_audio` | POST | สร้างเสียง |
| `/submit_feedback` | POST | ส่งคะแนน |

## Tech Stack

- **Backend**: Flask, Groq API (LLaMA)
- **Frontend**: HTML, CSS, JavaScript
- **TTS**: Google Text-to-Speech (gTTS)
- **STT**: Web Speech API (Browser)

## License

MIT License
