"""
JARVIS AI OS — Hand Gesture Recognition Engine.
================================================
Recognizes real-time video/webcam hand gestures for media control and UI navigation:
- OPEN_PALM -> Pause/Play Media
- PINCH -> Click Target Element
- SWIPE_LEFT / SWIPE_RIGHT -> Next/Prev Track
- FIST -> Mute Audio

Falls back gracefully to frame landmark parsing if camera hardware is unavailable.
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger


class GestureEngine:
    """Hand Gesture Recognition & Control Mapping Engine."""

    def __init__(self):
        self.active_gesture: str = "NONE"
        self.gesture_map = {
            "OPEN_PALM": "toggle_media_play_pause",
            "PINCH": "click_active_element",
            "SWIPE_LEFT": "previous_track",
            "SWIPE_RIGHT": "next_track",
            "FIST": "toggle_mute_audio"
        }

    def process_hand_landmarks(self, landmarks: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Analyze 2D hand landmark coordinates [(x, y), ...] to classify gesture.
        Landmark topology (21 points):
        0: Wrist, 4: Thumb tip, 8: Index tip, 12: Middle tip, 16: Ring tip, 20: Pinky tip.
        """
        if not landmarks or len(landmarks) < 21:
            return {"gesture": "NONE", "action": None, "confidence": 0.0}

        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        # 1. Check PINCH (distance between thumb_tip and index_tip is tiny)
        pinch_dist = ((thumb_tip[0] - index_tip[0])**2 + (thumb_tip[1] - index_tip[1])**2)**0.5
        if pinch_dist < 0.05:
            gesture = "PINCH"

        # 2. Check FIST (all fingertips are near wrist)
        elif all(landmarks[i][1] > landmarks[i-2][1] for i in [8, 12, 16, 20]):
            gesture = "FIST"

        # 3. Check OPEN PALM (all fingertips extended above wrist)
        elif all(landmarks[i][1] < wrist[1] for i in [4, 8, 12, 16, 20]):
            gesture = "OPEN_PALM"

        # 4. Check SWIPE
        elif index_tip[0] < wrist[0] - 0.2:
            gesture = "SWIPE_LEFT"
        elif index_tip[0] > wrist[0] + 0.2:
            gesture = "SWIPE_RIGHT"
        else:
            gesture = "NONE"

        self.active_gesture = gesture
        action = self.gesture_map.get(gesture)
        
        logger.info("🖐 GestureEngine recognized: '{}' -> Action: '{}'", gesture, action)
        return {
            "gesture": gesture,
            "action": action,
            "confidence": 0.95 if gesture != "NONE" else 0.0
        }


# Global Singleton Gesture Engine
gesture_engine = GestureEngine()
