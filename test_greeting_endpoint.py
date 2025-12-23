"""
ทดสอบ endpoint /greeting
"""
from flask import Flask, jsonify
import random

app = Flask(__name__)

@app.route("/greeting", methods=["GET"])
def greeting():
    """ส่งข้อความทักทายเริ่มต้น"""
    greetings = [
        "สวัสดีค่ะ! ดิฉันชื่อไอว่า ยินดีต้อนรับเข้าสู่ระบบค่ะ มีอะไรให้ช่วยไหมคะ",
        "สวัสดีค่ะ! ดิฉันไอว่า ผู้ช่วยอัจฉริยะของวิทยาลัยพณิชยการธนบุรี ยินดีให้บริการค่ะ",
        "สวัสดีค่ะ! ดิฉันไอว่าค่ะ มีคำถามอะไรเกี่ยวกับการรับสมัคร หลักสูตร หรืออาชีพ สอบถามได้เลยนะคะ"
    ]
    message = random.choice(greetings)
    return jsonify({"ok": True, "message": message})

# ทดสอบ
with app.test_client() as client:
    response = client.get('/greeting')
    data = response.get_json()

    print("=" * 60)
    print("ทดสอบ /greeting endpoint")
    print("=" * 60)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {data}")
    print(f"Message: {data.get('message')}")
    print("=" * 60)

    if response.status_code == 200 and data.get('ok'):
        print("✅ Endpoint ทำงานได้ถูกต้อง!")
    else:
        print("❌ Endpoint มีปัญหา")
