import threading
import time
import re
from collections import deque


class State:
    def __init__(self):
        self.lock = threading.RLock()

        # Audio mute states
        self.mute_mic = False
        self.mute_system = False

        # Text accumulation (global — what shows in the overlay)
        self.current_line = ""
        self.partial_buffer = ""
        self.full_transcript = ""

        # Duplicate prevention tracking
        self._last_final_text = ""
        self._last_partial_text = ""
        self._last_final_time = 0
        self._last_partial_time = 0
        self._final_history = deque(maxlen=5)
        self._partial_history = deque(maxlen=3)

        # Tracking
        self.last_source = None
        self.last_audio_ts = time.time()
        self.last_final_ts = time.time()
        self.last_partial_update = 0

        # AI state
        self.is_ai_responding = False
        self.current_question = ""
        self.ai_response_buffer = ""
        self.ai_streaming_complete = False

        # Buffer for audio during AI response
        self.audio_during_ai_response = ""
        self.buffered_audio = ""

        # 🔥 NEW: Per-source live line tracking for screenshot snapshots
        self.system_current_line = ""
        self.system_partial_buffer = ""
        self.last_system_update = 0

        self.mic_current_line = ""
        self.mic_partial_buffer = ""
        self.last_mic_update = 0

        # Speech config
        self._speech_config = None

        # Update event for SSE
        self.update_event = threading.Event()
        self._update_time = time.time()

    # ---------------- PROPERTIES ----------------
    @property
    def speech_config(self):
        return self._speech_config

    @speech_config.setter
    def speech_config(self, config):
        self._speech_config = config

    # ---------------- MAIN STT PROCESSING ----------------
    def process_stt_text(self, source: str, text: str, is_final: bool):
        """Process STT text from audio sources - FIXED DUPLICATE ISSUE."""
        with self.lock:
            text = text.strip()
            if not text:
                return

            current_time = time.time()

            # Duplicate check first
            if self._is_duplicate(text, is_final, current_time):
                print(f"🔄 SKIPPING duplicate {source} text: '{text}' (final: {is_final})")
                return

            print(f"🎯 STT Process: {source} - '{text}' (final: {is_final})")

            # Mute filtering
            if (source == "mic" and self.mute_mic) or (source == "system" and self.mute_system):
                print(f"🔇 {source} is muted - ignoring text")
                return

            # Buffer during AI response
            if self.is_ai_responding:
                print(f"📥 AI responding - buffering {source} audio: '{text}'")
                if self.buffered_audio:
                    self.buffered_audio += " " + text
                else:
                    self.buffered_audio = text
                return

            # Clean text
            text = self._clean_text(text)

            # 🔥 Track per-source live line for screenshot snapshots
            if source == "system":
                self._update_source_line(
                    is_system=True, text=text,
                    is_final=is_final, current_time=current_time
                )
            elif source == "mic":
                self._update_source_line(
                    is_system=False, text=text,
                    is_final=is_final, current_time=current_time
                )

            # Global accumulation (for overlay display)
            if is_final:
                if text and self._should_add_to_current_line(text):
                    if not self.current_line:
                        self.current_line = text
                    else:
                        if not self.current_line.endswith(text):
                            self.current_line += " " + text

                    self._last_final_text = text
                    self._last_final_time = current_time
                    self._final_history.append(text)
                    print(f"✅ Final added: '{text}' -> Current: '{self.current_line}'")

                self.partial_buffer = ""

                if self.full_transcript:
                    self.full_transcript += " "
                self.full_transcript += text
            else:
                if text:
                    self.partial_buffer = text
                    self._last_partial_text = text
                    self._last_partial_time = current_time
                    self._partial_history.append(text)
                    print(f"↗️ Partial updated: '{text}'")

            # Update tracking
            self.last_source = source
            self.last_audio_ts = current_time

            if is_final:
                self.last_final_ts = current_time
            else:
                self.last_partial_update = current_time

            self.update_event.set()
            self._update_time = current_time

    # ---------------- PER-SOURCE LINE TRACKING ----------------
    def _update_source_line(self, is_system: bool, text: str, is_final: bool, current_time: float):
        """Maintain per-source committed line + live partial buffer."""
        if is_system:
            if is_final:
                if not self.system_current_line:
                    self.system_current_line = text
                elif not self.system_current_line.endswith(text):
                    self.system_current_line += " " + text
                self.system_partial_buffer = ""
                self.last_system_update = current_time
            else:
                self.system_partial_buffer = text
                self.last_system_update = current_time
        else:  # mic
            if is_final:
                if not self.mic_current_line:
                    self.mic_current_line = text
                elif not self.mic_current_line.endswith(text):
                    self.mic_current_line += " " + text
                self.mic_partial_buffer = ""
                self.last_mic_update = current_time
            else:
                self.mic_partial_buffer = text
                self.last_mic_update = current_time

    def get_live_context(self):
        """
        🔥 Snapshot current live speech (used at screenshot capture time).
        Combines committed line + live partial for both sources.
        Prefers system (interviewer) audio, falls back to mic.
        """
        with self.lock:
            current_time = time.time()

            # System (interviewer)
            system_parts = []
            if self.system_current_line:
                system_parts.append(self.system_current_line.strip())
            if self.system_partial_buffer:
                partial = self.system_partial_buffer.strip()
                if partial and (not system_parts or not system_parts[-1].endswith(partial)):
                    system_parts.append(partial)
            system_text = " ".join(system_parts).strip()

            # Mic
            mic_parts = []
            if self.mic_current_line:
                mic_parts.append(self.mic_current_line.strip())
            if self.mic_partial_buffer:
                partial = self.mic_partial_buffer.strip()
                if partial and (not mic_parts or not mic_parts[-1].endswith(partial)):
                    mic_parts.append(partial)
            mic_text = " ".join(mic_parts).strip()

            # Prefer system (interviewer); fall back to mic
            interviewer_text = system_text or mic_text

            return {
                "system_current_line": self.system_current_line,
                "system_partial_buffer": self.system_partial_buffer,
                "system_text": system_text,
                "mic_current_line": self.mic_current_line,
                "mic_partial_buffer": self.mic_partial_buffer,
                "mic_text": mic_text,
                "interviewer_text": interviewer_text,
                "system_age_sec": (current_time - self.last_system_update)
                                    if self.last_system_update else 999.0,
                "mic_age_sec": (current_time - self.last_mic_update)
                                    if self.last_mic_update else 999.0,
            }

    # ---------------- DUPLICATE / CLEANING HELPERS ----------------
    def _is_duplicate(self, text: str, is_final: bool, current_time: float) -> bool:
        if is_final:
            if text == self._last_final_text and (current_time - self._last_final_time) < 0.05:
                return True
            if text in self._final_history:
                return True
        else:
            if text == self._last_partial_text and (current_time - self._last_partial_time) < 0.05:
                return True
            if text in self._partial_history:
                return True

        clean_text = re.sub(r'[.,;!?]+$', '', text)
        if is_final:
            clean_last = re.sub(r'[.,;!?]+$', '', self._last_final_text)
            if clean_text == clean_last and (current_time - self._last_final_time) < 0.1:
                return True
        else:
            clean_last = re.sub(r'[.,;!?]+$', '', self._last_partial_text)
            if clean_text == clean_last and (current_time - self._last_partial_time) < 0.1:
                return True

        return False

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'[.,;!?]+$', '', text)

        words = text.split()
        if len(words) > 1:
            cleaned_words = []
            for i, word in enumerate(words):
                if i == 0 or word.lower() != words[i - 1].lower():
                    cleaned_words.append(word)
            text = ' '.join(cleaned_words)

        return text

    def _should_add_to_current_line(self, new_text: str) -> bool:
        if not new_text or not self.current_line:
            return True
        if self.current_line.endswith(new_text):
            return False

        words = new_text.lower().split()
        current_words = self.current_line.lower().split()
        if len(words) > 0 and all(word in ' '.join(current_words[-5:]) for word in words[-3:]):
            return False
        return True

    # ---------------- SSE SNAPSHOT ----------------
    def get_text_for_sse(self):
        with self.lock:
            current_time = time.time()
            time_since_audio = current_time - self.last_audio_ts
            time_since_partial = current_time - self.last_partial_update

            has_partial = (
                len(self.partial_buffer) > 0 and
                time_since_partial < 1.5 and
                time_since_audio < 3.0
            )

            return {
                "current_line": self.current_line,
                "partial_buffer": self.partial_buffer,
                "last_source": self.last_source,
                "last_audio_seconds_ago": time_since_audio,
                "has_partial": has_partial,
                "timestamp": current_time,
                "is_ai_responding": self.is_ai_responding,
            }

    # ---------------- RESET METHODS ----------------
    def _clear_live_sources(self):
        """🔥 Helper to clear per-source live tracking."""
        self.system_current_line = ""
        self.system_partial_buffer = ""
        self.mic_current_line = ""
        self.mic_partial_buffer = ""
        self.last_system_update = 0
        self.last_mic_update = 0

    def reset_for_answer_button(self, question):
        with self.lock:
            self.current_line = ""
            self.partial_buffer = ""
            self.buffered_audio = ""

            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()

            self._clear_live_sources()

            self.is_ai_responding = True
            self.current_question = question
            self.ai_response_buffer = ""
            self.ai_streaming_complete = False

            self.update_event.set()
            print(f"🤖 AI started responding to FRESH question: '{question}'")

    def complete_ai_response(self, response):
        with self.lock:
            self.is_ai_responding = False
            self.ai_response_buffer = response
            self.ai_streaming_complete = True

            self.current_line = ""
            self.partial_buffer = ""
            self.buffered_audio = ""

            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()

            self._clear_live_sources()

            self.update_event.set()
            print("✅ AI response complete, ready for next question")

    def reset_for_clear_button(self):
        with self.lock:
            self.current_line = ""
            self.partial_buffer = ""
            self.buffered_audio = ""
            self.full_transcript = ""
            self.last_source = None

            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            self._last_final_time = time.time()
            self._last_partial_time = time.time()

            self._clear_live_sources()

            self.update_event.set()
            print("🔄 Cleared all text for fresh start")

    def fresh_start(self):
        with self.lock:
            self.current_line = ""
            self.partial_buffer = ""
            self.full_transcript = ""
            self.buffered_audio = ""
            self.audio_during_ai_response = ""
            self.last_source = None
            self.ai_response_buffer = ""

            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            self._last_final_time = time.time()
            self._last_partial_time = time.time()

            self._clear_live_sources()

            self.last_audio_ts = time.time()
            self.last_final_ts = time.time()
            self.last_partial_update = 0

            self.update_event.set()
            print("🔄 COMPLETE fresh start - all text cleared")

    def set_mute_state(self, source, muted):
        with self.lock:
            if source == "mic":
                self.mute_mic = muted
                if not muted:
                    self.fresh_start()
            elif source == "system":
                self.mute_system = muted
                if not muted:
                    self.fresh_start()

            print(f"🔊 {source} {'muted' if muted else 'unmuted'}")
            self.update_event.set()


# Global state instance
state = State()