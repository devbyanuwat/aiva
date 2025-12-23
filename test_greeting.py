"""
ทดสอบระบบทักทาย AIVA
"""
import json

# โหลด FAQ
with open('faq.json', 'r', encoding='utf-8') as f:
    faq_data = json.load(f)

def check_faq(question):
    """ตรวจสอบว่าคำถามตรงกับ FAQ หรือไม่"""
    question_lower = question.lower().strip()
    for faq in faq_data:
        keywords = faq.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in question_lower:
                return faq.get("answer", "")
    return None

# ทดสอบคำทักทาย
test_questions = [
    "สวัสดี",
    "หวัดดีครับ",
    "ว่าไงอ้ายวา",
    "Hello AIVA",
    "เธอชื่ออะไร",
    "ขอบคุณนะ",
    "บายบาย",
]

print("=" * 60)
print("ทดสอบระบบทักทาย AIVA")
print("=" * 60)

for q in test_questions:
    answer = check_faq(q)
    status = "✅ ตอบได้" if answer else "❌ ไม่ตรง FAQ"
    print(f"\n{status}")
    print(f"คำถาม: {q}")
    if answer:
        print(f"คำตอบ: {answer}")

print("\n" + "=" * 60)
print(f"✅ โหลด FAQ สำเร็จ ({len(faq_data)} รายการ)")
print("=" * 60)
