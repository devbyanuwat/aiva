# vision.py
import cv2
import threading
import time

class HumanDetector:
    def __init__(self, camera_index=0, cascade_path=None, detection_callback=None, idle_callback=None, detection_cooldown=3):
        # cascade_path: path to haarcascade_frontalface_default.xml
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.cap = cv2.VideoCapture(camera_index)
        self.running = False
        self.detection_callback = detection_callback
        self.idle_callback = idle_callback
        self.detection_cooldown = detection_cooldown
        self._last_detection_time = 0

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False
        try:
            self.cap.release()
        except:
            pass

    def _loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60,60))
            now = time.time()
            if len(faces) > 0:
                # only call callback if not called in the last cooldown seconds
                if now - self._last_detection_time > self.detection_cooldown:
                    self._last_detection_time = now
                    if self.detection_callback:
                        try:
                            self.detection_callback()
                        except Exception as e:
                            print("detection_callback error:", e)
            else:
                # optionally call idle callback
                if self.idle_callback:
                    try:
                        self.idle_callback()
                    except Exception as e:
                        print("idle_callback error:", e)
            # small sleep to reduce CPU
            time.sleep(0.1)
