import pdfplumber
import os
import glob
import time
import json
import logging
from openai import OpenAI

# สร้าง logger สำหรับ module นี้
logger = logging.getLogger(__name__)

class PdfAIEngine:
    def __init__(self, pdf_folder_path: str, api_key: str):
        logger.info("Initializing PdfAIEngine...")
        self.knowledge_base = ""
        self.client = None
        self.faq_data = []

        # ใช้ API Key จาก parameter หรือ environment variable
        final_api_key = api_key or os.environ.get("GROQ_API_KEY", "")

        # โหลด FAQ
        self._load_faq()

        if not os.path.isdir(pdf_folder_path):
            self.knowledge_base = "ไม่พบโฟลเดอร์ข้อมูล"
            logger.error(f"PDF folder not found: {pdf_folder_path}")
        else:
            logger.info(f"Loading knowledge base from: {pdf_folder_path}")
            self.knowledge_base = self._extract_text_from_folder(pdf_folder_path)
            logger.info(f"Knowledge base loaded successfully ({len(self.knowledge_base)} characters)")

        if not final_api_key:
            logger.error("GROQ_API_KEY not found")
            return

        try:
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=final_api_key,
                max_retries=0,  # Disable automatic retries to prevent worker timeout
                timeout=30.0    # Set request timeout to 30 seconds
            )
            logger.info("Groq AI client connected successfully")
        except Exception as e:
            logger.error(f"Groq initialization error: {e}", exc_info=True)
            self.client = None

    def _load_faq(self):
        """โหลดข้อมูล FAQ จากไฟล์ faq.json"""
        faq_file = "faq.json"
        try:
            if os.path.exists(faq_file):
                with open(faq_file, 'r', encoding='utf-8') as f:
                    self.faq_data = json.load(f)
                logger.info(f"FAQ loaded successfully ({len(self.faq_data)} entries)")
            else:
                logger.warning(f"FAQ file not found: {faq_file}")
        except Exception as e:
            logger.error(f"Error loading FAQ: {e}", exc_info=True)
            self.faq_data = []

    def _check_faq(self, question: str) -> str:
        """ตรวจสอบว่าคำถามตรงกับ FAQ หรือไม่"""
        question_lower = question.lower().strip()

        for faq in self.faq_data:
            keywords = faq.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    answer = faq.get("answer", "")
                    logger.info(f"FAQ match found for keyword: '{keyword}'")
                    logger.debug(f"FAQ answer: {answer[:100]}...")
                    return answer

        logger.debug("No FAQ match found")
        return None

    def _extract_text_from_folder(self, folder_path: str) -> str:
        all_text = ""
        pdf_count = 0
        txt_count = 0

        # 1. อ่าน PDF
        pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
        logger.debug(f"Found {len(pdf_files)} PDF files")
        for pdf_path in pdf_files:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t: all_text += t + "\n"
                pdf_count += 1
                logger.debug(f"Extracted text from PDF: {os.path.basename(pdf_path)}")
            except Exception as e:
                logger.warning(f"Failed to extract PDF {pdf_path}: {e}")

        # 2. อ่าน TXT
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        logger.debug(f"Found {len(txt_files)} TXT files")
        for txt_path in txt_files:
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    all_text += f.read() + "\n"
                txt_count += 1
                logger.debug(f"Extracted text from TXT: {os.path.basename(txt_path)}")
            except Exception as e:
                logger.warning(f"Failed to extract TXT {txt_path}: {e}")

        logger.info(f"Extracted {pdf_count} PDFs and {txt_count} TXT files")
        return all_text if all_text else "ไม่มีข้อมูล"

    def _get_relevant_context(self, question: str, max_chars=6000) -> str:
        """ เลือกข้อมูลที่เกี่ยวข้อง เพื่อส่งให้ AI (ลดขนาดข้อมูลป้องกัน Error) """
        full_text = self.knowledge_base
        logger.debug(f"Full knowledge base size: {len(full_text)} chars")

        if len(full_text) < max_chars:
            logger.debug("Using full knowledge base (smaller than max_chars)")
            return full_text

        chunk_size = 1000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        logger.debug(f"Split knowledge base into {len(chunks)} chunks")

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
        logger.debug(f"Selected context size: {len(selected_text)} chars from {len(top_chunks)} chunks")
        return selected_text

    def find_answer(self, user_question: str) -> str:
        logger.info(f"Processing question: {user_question}")

        # ตรวจสอบ FAQ ก่อน (ตอบเร็วกว่า ไม่ต้องเรียก AI)
        faq_answer = self._check_faq(user_question)
        if faq_answer:
            logger.info("Answered from FAQ (no AI call needed)")
            return faq_answer

        if not self.client:
            logger.error("AI client not initialized")
            return "ระบบ AI ขัดข้อง"

        context = self._get_relevant_context(user_question)
        logger.info(f"Calling AI with context ({len(context)} chars)...")
        
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

        retry_delay = 0.5  # Start with 0.5 seconds
        for model_index, model in enumerate(models_to_try):
            try:
                logger.info(f"Trying AI model: {model}")
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_question}
                    ],
                    model=model,
                    temperature=0.5,
                    max_tokens=400,
                )
                answer = chat_completion.choices[0].message.content.strip()
                logger.info(f"AI response received from {model} ({len(answer)} chars)")
                logger.debug(f"AI answer preview: {answer[:100]}...")
                return answer

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate_limit" in error_msg.lower():
                    logger.warning(f"Model {model} quota exceeded (429) - switching to backup model")
                    # Only sleep if there are more models to try
                    if model_index < len(models_to_try) - 1:
                        logger.info(f"Waiting {retry_delay}s before trying next model...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 3)  # Exponential backoff, max 3s
                    continue
                elif "timeout" in error_msg.lower():
                    logger.error(f"Timeout with model {model} - trying next model")
                    continue
                else:
                    logger.error(f"API error with model {model}: {error_msg}", exc_info=True)
                    # Try next model instead of returning immediately
                    if model_index < len(models_to_try) - 1:
                        continue
                    return "ขออภัย ระบบขัดข้องชั่วคราว"

        logger.error("All AI models exhausted - quota limit reached")
        return "ขออภัย ขณะนี้มีผู้ใช้งานจำนวนมาก กรุณารอสักครู่แล้วลองใหม่"