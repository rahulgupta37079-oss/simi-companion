"""Local-only OpenCV webcam emotion & crying-distress heuristic detector."""

from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger("simi.emotion")


class LocalEmotionDetector:
    """Detects potential crying/distress locally using OpenCV Haar cascades without saving frames."""

    def __init__(self) -> None:
        self._cv2 = None
        self.face_cascade = None
        self.eye_cascade = None
        self.smile_cascade = None
        self._distress_streak = 0

    def _ensure_cv2(self) -> bool:
        if self._cv2 is not None:
            return True
        try:
            import cv2  # type: ignore

            base = cv2.data.haarcascades
            self.face_cascade = cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml")
            self.eye_cascade = cv2.CascadeClassifier(base + "haarcascade_eye.xml")
            self.smile_cascade = cv2.CascadeClassifier(base + "haarcascade_smile.xml")
            self._cv2 = cv2
            return True
        except Exception as exc:
            logger.warning("OpenCV unavailable for webcam emotion check: %s", exc)
            return False

    def sample_webcam(self) -> Dict[str, object]:
        """Capture a single frame in-memory, evaluate distress cues, and release camera immediately."""
        if not self._ensure_cv2():
            return {"camera_ok": False, "face_detected": False, "distress_alert": False, "mood_hint": "cv2_unavailable"}
        cv2 = self._cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return {"camera_ok": False, "face_detected": False, "distress_alert": False, "mood_hint": "no_camera"}

        try:
            # Warm up 2 frames for auto-exposure
            ret, frame = False, None
            for _ in range(3):
                ret, frame = cap.read()
            if not ret or frame is None:
                return {"camera_ok": False, "face_detected": False, "distress_alert": False, "mood_hint": "read_failed"}

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))
            if len(faces) == 0:
                # Could be head-down crying or stepped away
                return {"camera_ok": True, "face_detected": False, "distress_alert": False, "mood_hint": "away"}

            x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
            roi_gray = gray[y : y + h, x : x + w]
            upper_face = roi_gray[0 : int(h * 0.55), :]
            lower_face = roi_gray[int(h * 0.55) :, :]

            eyes = self.eye_cascade.detectMultiScale(upper_face, scaleFactor=1.1, minNeighbors=6, minSize=(20, 20))
            smiles = self.smile_cascade.detectMultiScale(lower_face, scaleFactor=1.7, minNeighbors=20, minSize=(25, 25))

            if len(smiles) > 0:
                self._distress_streak = 0
                return {"camera_ok": True, "face_detected": True, "distress_alert": False, "mood_hint": "positive"}

            # Squinting / closed / teary eyes with no smile across consecutive checks
            if len(eyes) == 0:
                self._distress_streak += 1
            else:
                self._distress_streak = max(0, self._distress_streak - 1)

            alert = self._distress_streak >= 3
            if alert:
                self._distress_streak = 0
            return {
                "camera_ok": True,
                "face_detected": True,
                "distress_alert": alert,
                "mood_hint": "distressed" if alert else "focused",
            }
        except Exception as exc:
            logger.debug("Webcam emotion check error: %s", exc)
            return {"camera_ok": False, "face_detected": False, "distress_alert": False, "mood_hint": "error"}
        finally:
            cap.release()


emotion_detector = LocalEmotionDetector()
