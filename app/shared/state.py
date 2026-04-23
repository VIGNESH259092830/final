import threading
import time
import re
from collections import deque

class State:
    def __init__(self):
        self.lock = threading.RLock()
        
        # Audio mute states
        self.mute_mic = False  # Mic starts UNMUTED
        self.mute_system = False
        
        # Text accumulation
        self.current_line = ""  # Continuous text accumulation
        self.partial_buffer = ""  # For real-time partial text
        self.full_transcript = ""
        
        # 🔥 NEW: Duplicate prevention tracking
        self._last_final_text = ""  # Last final text received
        self._last_partial_text = ""  # Last partial text received
        self._last_final_time = 0  # When last final text was received
        self._last_partial_time = 0  # When last partial text was received
        self._final_history = deque(maxlen=5)  # Keep last 5 final texts
        self._partial_history = deque(maxlen=3)  # Keep last 3 partial texts
        
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
        self.buffered_audio = ""  # Buffer for audio during AI response
        
        # Speech config
        self._speech_config = None
        
        # Update event for SSE
        self.update_event = threading.Event()
        self._update_time = time.time()
    
    @property
    def speech_config(self):
        return self._speech_config
    
    @speech_config.setter
    def speech_config(self, config):
        self._speech_config = config
    
    def process_stt_text(self, source: str, text: str, is_final: bool):
        """Process STT text from audio sources - FIXED DUPLICATE ISSUE"""
        with self.lock:
            text = text.strip()
            if not text:
                return
            
            current_time = time.time()
            
            # 🔥 CRITICAL FIX: Check for duplicates BEFORE anything else
            if self._is_duplicate(text, is_final, current_time):
                print(f"🔄 SKIPPING duplicate {source} text: '{text}' (final: {is_final})")
                return
            
            print(f"🎯 STT Process: {source} - '{text}' (final: {is_final})")
            
            # Apply mute filtering
            if (source == "mic" and self.mute_mic) or (source == "system" and self.mute_system):
                print(f"🔇 {source} is muted - ignoring text")
                return
            
            # If AI is responding, buffer audio for next question
            if self.is_ai_responding:
                print(f"📥 AI responding - buffering {source} audio: '{text}'")
                if self.buffered_audio:
                    self.buffered_audio += " " + text
                else:
                    self.buffered_audio = text
                return
            
            # Clean text
            text = self._clean_text(text)
            
            # Process text
            if is_final:
                # FINAL TEXT: Add to current line
                if text and self._should_add_to_current_line(text):
                    if not self.current_line:
                        self.current_line = text
                    else:
                        # Add space only if not duplicate ending
                        if not self.current_line.endswith(text):
                            self.current_line += " " + text
                    
                    # Update duplicate tracking
                    self._last_final_text = text
                    self._last_final_time = current_time
                    self._final_history.append(text)
                    
                    print(f"✅ Final added: '{text}' -> Current: '{self.current_line}'")
                
                # Clear partial buffer
                self.partial_buffer = ""
                
                # Add to full transcript
                if self.full_transcript:
                    self.full_transcript += " "
                self.full_transcript += text
                
            else:
                # PARTIAL TEXT: Update partial buffer
                if text:
                    self.partial_buffer = text
                    
                    # Update duplicate tracking
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
            
            # Trigger update
            self.update_event.set()
            self._update_time = current_time
    
    def _is_duplicate(self, text: str, is_final: bool, current_time: float) -> bool:
        """Check if text is a duplicate that should be skipped"""
        
        # Skip if same text was just processed (within 50ms)
        if is_final:
            if text == self._last_final_text and (current_time - self._last_final_time) < 0.05:
                return True
            # Check history
            if text in self._final_history:
                return True
        else:
            if text == self._last_partial_text and (current_time - self._last_partial_time) < 0.05:
                return True
            # Check history
            if text in self._partial_history:
                return True
        
        # Check for punctuation variations (hello. vs hello)
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
        """Clean and normalize text"""
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove trailing punctuation
        text = re.sub(r'[.,;!?]+$', '', text)
        
        # Remove consecutive duplicate words
        words = text.split()
        if len(words) > 1:
            cleaned_words = []
            for i, word in enumerate(words):
                if i == 0 or word.lower() != words[i-1].lower():
                    cleaned_words.append(word)
            text = ' '.join(cleaned_words)
        
        return text
    
    def _should_add_to_current_line(self, new_text: str) -> bool:
        """Check if new text should be added to current line"""
        if not new_text or not self.current_line:
            return True
        
        # If new text is already at the end of current line, skip
        if self.current_line.endswith(new_text):
            return False
        
        # Check if new text contains parts already in current line
        words = new_text.lower().split()
        current_words = self.current_line.lower().split()
        
        # If all words are already in current line, skip
        if len(words) > 0 and all(word in ' '.join(current_words[-5:]) for word in words[-3:]):
            return False
        
        return True
    
    def get_text_for_sse(self):
        """Get text for SSE - format frontend expects"""
        with self.lock:
            current_time = time.time()
            time_since_audio = current_time - self.last_audio_ts
            time_since_partial = current_time - self.last_partial_update
            
            # Show partial if recent (within 1.5 seconds)
            has_partial = (len(self.partial_buffer) > 0 and 
                          time_since_partial < 1.5 and
                          time_since_audio < 3.0)
            
            return {
                "current_line": self.current_line,
                "partial_buffer": self.partial_buffer,
                "last_source": self.last_source,
                "last_audio_seconds_ago": time_since_audio,
                "has_partial": has_partial,
                "timestamp": current_time
            }
    
    def reset_for_answer_button(self, question):
        """Reset state when AI starts answering"""
        with self.lock:
            # Clear ALL text accumulators for fresh start
            self.current_line = ""  # Clear accumulated text
            self.partial_buffer = ""  # Clear partial text
            self.buffered_audio = ""  # Clear buffered audio
            
            # Clear duplicate tracking
            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            
            self.is_ai_responding = True
            self.current_question = question
            self.ai_response_buffer = ""
            self.ai_streaming_complete = False
            
            # Trigger update for immediate UI refresh
            self.update_event.set()
            print(f"🤖 AI started responding to FRESH question: '{question}'")
    
    def complete_ai_response(self, response):
        """Complete AI response and prepare for next question"""
        with self.lock:
            self.is_ai_responding = False
            self.ai_response_buffer = response
            self.ai_streaming_complete = True
            
            # Clear for next question
            self.current_line = ""
            self.partial_buffer = ""
            self.buffered_audio = ""
            
            # Clear duplicate tracking for fresh start
            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            
            self.update_event.set()
            print(f"✅ AI response complete, ready for next question")
    
    def reset_for_clear_button(self):
        """Reset for clear button - fresh start"""
        with self.lock:
            self.current_line = ""
            self.partial_buffer = ""
            self.buffered_audio = ""
            self.full_transcript = ""
            self.last_source = None
            
            # Clear duplicate tracking
            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            self._last_final_time = time.time()
            self._last_partial_time = time.time()
            
            self.update_event.set()
            print("🔄 Cleared all text for fresh start")
    
    def fresh_start(self):
        """Complete fresh start - clear everything"""
        with self.lock:
            self.current_line = ""
            self.partial_buffer = ""
            self.full_transcript = ""
            self.buffered_audio = ""
            self.audio_during_ai_response = ""
            self.last_source = None
            self.ai_response_buffer = ""
            
            # Clear duplicate tracking
            self._last_final_text = ""
            self._last_partial_text = ""
            self._final_history.clear()
            self._partial_history.clear()
            self._last_final_time = time.time()
            self._last_partial_time = time.time()
            
            # Reset timestamps
            self.last_audio_ts = time.time()
            self.last_final_ts = time.time()
            self.last_partial_update = 0
            
            self.update_event.set()
            print("🔄 COMPLETE fresh start - all text cleared")
    
    def set_mute_state(self, source, muted):
        """Set mute state for audio source - clear text when unmuting"""
        with self.lock:
            if source == "mic":
                self.mute_mic = muted
                if not muted:  # When unmuting
                    self.fresh_start()
            elif source == "system":
                self.mute_system = muted
                if not muted:  # When unmuting
                    self.fresh_start()
            
            print(f"🔊 {source} {'muted' if muted else 'unmuted'}")
            self.update_event.set()

# Global state instance
state = State()
# In app/shared/state.py - add this method

# In app/shared/state.py - replace the get_text_for_sse method

# In app/shared/state.py - REPLACE with this version

def get_text_for_sse(self):
    """
    Get text data for SSE - Include AI status for UI feedback
    """
    with self.lock:
        current_time = time.time()
        time_since_audio = current_time - self.last_audio_ts
        time_since_partial = current_time - self.last_partial_update
        
        # Show partial if recent (within 1.5 seconds)
        has_partial = (len(self.partial_buffer) > 0 and 
                      time_since_partial < 1.5 and
                      time_since_audio < 3.0)
        
        # 🔥 CRITICAL: Return current_line even during AI response (but empty if AI responding)
        # This allows the frontend to know AI is responding
        return {
            "current_line": self.current_line,  # Don't clear - let frontend handle
            "partial_buffer": self.partial_buffer,
            "last_source": self.last_source,
            "last_audio_seconds_ago": time_since_audio,
            "has_partial": has_partial,
            "timestamp": current_time,
            "is_ai_responding": self.is_ai_responding  # 🔥 ADD THIS for frontend to know
        }