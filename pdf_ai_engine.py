import pdfplumber
import os
import glob
import time
from openai import OpenAI

class PdfAIEngine:
    def __init__(self, pdf_folder_path: str, api_key: str):
        self.knowledge_base = "" 
        self.client = None
        
        # ใช้ API Key จาก parameter หรือ environment variable
        final_api_key = api_key or os.environ.get("GROQ_API_KEY", "")

        if not os.path.isdir(pdf_folder_path):
            self.knowledge_base = "ไม่พบโฟลเดอร์ข้อมูล"
        else:
            print(f"📂 กำลังโหลดข้อมูลจาก: {pdf_folder_path}")
            self.knowledge_base = self._extract_text_from_folder(pdf_folder_path) 
            print(f"✅ อ่านข้อมูลสำเร็จ (รวม {len(self.knowledge_base)} ตัวอักษร)")
        
        if not final_api_key:
            print("❌ ไม่พบ API KEY")
            return

        try:
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=final_api_key
            )
            print(f"✅ AI เชื่อมต่อสำเร็จ!")
        except Exception as e:
            print(f"❌ Groq Init Error: {e}")
            self.client = None

    def _extract_text_from_folder(self, folder_path: str) -> str:
        all_text = ""
        # 1. อ่าน PDF
        for pdf_path in glob.glob(os.path.join(folder_path, '*.pdf')):
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t: all_text += t + "\n"
            except: pass
        
        # 2. อ่าน TXT
        for txt_path in glob.glob(os.path.join(folder_path, '*.txt')):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    all_text += f.read() + "\n"
            except: pass

        return all_text if all_text else "ไม่มีข้อมูล"

    def _get_relevant_context(self, question: str, max_chars=6000) -> str:
        """ เลือกข้อมูลที่เกี่ยวข้อง เพื่อส่งให้ AI (ลดขนาดข้อมูลป้องกัน Error) """
        full_text = self.knowledge_base
        if len(full_text) < max_chars:
            return full_text

        chunk_size = 1000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        scored_chunks = []
        for i, chunk in enumerate(chunks):
            score = 0
            if question in chunk: score += 10
            
            keywords = question.split()
            for k in keywords:
                if len(k) > 2 and k in chunk: 
                    score += 1
            
            if i == 0: score += 2 
            
            scored_chunks.append((score, i, chunk))
        
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:8]
        top_chunks.sort(key=lambda x: x[1])
        
        selected_text = "\n...\n".join([chunk for _, _, chunk in top_chunks])
        return selected_text

    def find_answer(self, user_question: str) -> str:
        if not self.client: return "ระบบ AI ขัดข้อง"
            
        context = self._get_relevant_context(user_question)
        print(f"🤖 AI กำลังคิด (จากข้อมูล {len(context)} ตัวอักษร)...")
        
        # ==================================================================================
        # ⭐ PROMPT: บทบาทเจ้าหน้าที่ประชาสัมพันธ์วิทยาลัยพณิชยการธนบุรี
        # ==================================================================================
        system_prompt = f"""
        บทบาท: คุณคือเจ้าหน้าที่ประชาสัมพันธ์หญิง ของ "วิทยาลัยพณิชยการธนบุรี"
        บุคลิก: พูดจาสุภาพ เป็นมิตร กระชับ และช่วยเหลือผู้คน

        คำสั่งสำคัญที่สุด (Strict Rules):
        1. ให้ใช้ข้อมูลใน [Context] ด้านล่างนี้ ประกอบการตอบคำถาม
        2.`เวลาตอบเอาแค่ 3-5 บรรทัดก็พอ
        3. ต้องการคำตอบแบบสั้นกระชับและเข้าใจง่าย
        4. ***เงื่อนไขเด็ดขาด***: หากคำตอบ "ไม่มี" ใน [Context] หรือหาไม่เจอ -> ให้คุณตอบคำถามนั้นโดยใช้ "ความรู้ทั่วไปของคุณเอง" ได้เลยทันที
        5. ***ห้าม*** พูดประโยคเหล่านี้เด็ดขาด:
           - "ในเอกสารไม่ได้ระบุไว้"
           - "ไม่มีข้อมูลในบริบท"
           - "จากข้อมูลที่ให้มา"
           - "ฉันไม่ทราบเพราะไม่มีในเอกสาร"
        6. ให้ตอบเสมือนว่าคุณรู้เรื่องนั้นอยู่แล้ว ไม่ต้องอ้างอิงแหล่งที่มา
        7. รูปแบบการตอบ: พิมพ์เป็นข้อความธรรมดา (Plain Text) เท่านั้น ห้ามใช้ Markdown (เช่น **, ##, -) ห้ามทำตัวหนา ห้ามใส่สัญลักษณ์พิเศษ
        
        [Context ข้อมูลวิทยาลัย]
        ---
        {context}
        ---
        
        ผู้ใช้ถามว่า: {user_question}
        คำตอบของคุณ:
        """
        
        # รายชื่อโมเดลที่จะลองใช้ (ระบบ Auto-Switch แก้ Error 429)
        models_to_try = [
            "llama-3.3-70b-versatile",   # ตัวหลัก (ฉลาดสุด)
            "llama-3.1-8b-instant",      # ตัวรอง (เร็ว/โควต้าเยอะ)
            "gemma2-9b-it"               # ตัวสำรองสุดท้าย
        ]

        for model in models_to_try:
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_question}
                    ],
                    model=model,
                    temperature=0.5,
                    max_tokens=400,
                )
                return chat_completion.choices[0].message.content.strip()
            
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"⚠️ โมเดล {model} โควต้าเต็ม (429) -> กำลังสลับไปใช้ตัวสำรอง...")
                    time.sleep(1) # พักนิดนึงก่อนลองตัวใหม่
                    continue 
                else:
                    print(f"❌ API Error ({model}): {error_msg}")
                    return "ขออภัย ระบบขัดข้องชั่วคราว"
        
        return "ขออภัย ขณะนี้มีผู้ใช้งานจำนวนมาก กรุณารอสักครู่แล้วลองใหม่"