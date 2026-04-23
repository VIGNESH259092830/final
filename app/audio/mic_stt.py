import azure.cognitiveservices.speech as speechsdk
from app.shared.state import state
import time
import threading
import logging

logger = logging.getLogger(__name__)

# Global variables
_mic_recognizer = None
_mic_active = False
_on_mic_text_callback = None
_last_final_text = ""
_partial_buffer = ""
_last_partial_time = 0

# 🔥 ADD THESE GLOBAL VARIABLES FOR TRACKING
_pending_partials = {}  # Move to global scope
_sentence_history = []  # Track recent sentences
_last_processed_time = 0

def _create_mic_recognizer():
    """Create microphone recognizer"""
    try:
        audio_cfg = speechsdk.audio.AudioConfig(use_default_microphone=True)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=state.speech_config,
            audio_config=audio_cfg
        )
        
        # Set timeouts
        recognizer.properties.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "300000"  # 5 minutes
        )
        recognizer.properties.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            "30000"   # 30 seconds
        )
        
        return recognizer
        
    except Exception as e:
        logger.error(f"❌ Failed to create mic recognizer: {e}")
        return None

def _setup_mic_handlers(recognizer):
    """Setup microphone handlers - FIXED FOR NO DUPLICATION"""
    
    def recognizing_handler(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            text = evt.result.text.strip()
            if not text:
                return
                
            global _partial_buffer, _last_partial_time, _pending_partials
            current_time = time.time()
            
            # 🔥 SIMPLER DUPLICATE CHECK
            # Skip if same partial within 150ms
            if text == _partial_buffer and (current_time - _last_partial_time) < 0.15:
                return
            
            # Skip if partial matches last final text
            if text == _last_final_text:
                return
            
            # Update tracking
            _partial_buffer = text
            _last_partial_time = current_time
            
            # Store partial (with timestamp)
            _pending_partials[text] = current_time
            
            # Clean old partials (older than 1.5 seconds)
            for key, timestamp in list(_pending_partials.items()):
                if current_time - timestamp > 1.5:
                    del _pending_partials[key]
            
            # Send partial callback
            if _on_mic_text_callback:
                _on_mic_text_callback(text, is_final=False)
                logger.debug(f"🎤 Mic partial: {text}")
    
    def recognized_handler(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text.strip()
            if not text:
                return
                
            global _last_final_text, _partial_buffer, _pending_partials, _sentence_history, _last_processed_time
            current_time = time.time()
            
            # 🔥 CRITICAL FIX: Clear partial buffer
            _partial_buffer = ""
            
            # 🔥 CHECK 1: Skip if same as last final (exact match)
            if text == _last_final_text:
                logger.debug(f"🎤 Skipping exact duplicate: {text}")
                return
            
            # 🔥 CHECK 2: Skip if we just processed this within 300ms
            if (current_time - _last_processed_time) < 0.3:
                logger.debug(f"🎤 Skipping too recent: {text}")
                return
            
            # 🔥 CHECK 3: Skip if this text is in recent history
            # Check if this sentence is contained in or contains recent sentences
            text_lower = text.lower()
            skip_duplicate = False
            
            for past_sentence, past_time in _sentence_history:
                past_lower = past_sentence.lower()
                
                # If current text contains past text OR past text contains current text
                # AND they're within 2 seconds of each other
                if (text_lower.find(past_lower) >= 0 or past_lower.find(text_lower) >= 0) and \
                   (current_time - past_time) < 2.0:
                    skip_duplicate = True
                    logger.debug(f"🎤 Skipping overlapping text: '{text}' overlaps with '{past_sentence}'")
                    break
            
            if skip_duplicate:
                return
            
            # 🔥 CHECK 4: Check pending partials
            # If this final text matches a recent partial, skip it
            text_words = text.split()
            if len(text_words) > 0:
                for partial_text, partial_time in list(_pending_partials.items()):
                    partial_words = partial_text.split()
                    
                    # If final text starts with partial text and it's recent
                    if len(text_words) >= len(partial_words):
                        if ' '.join(text_words[:len(partial_words)]) == partial_text and \
                           (current_time - partial_time) < 1.0:
                            logger.debug(f"🎤 Skipping final matching recent partial: {text}")
                            # Remove this partial
                            if partial_text in _pending_partials:
                                del _pending_partials[partial_text]
                            return
            
            # 🔥 ALL CHECKS PASSED - PROCESS THIS TEXT
            
            # Update tracking
            _last_final_text = text
            _last_processed_time = current_time
            
            # Add to sentence history (keep last 5)
            _sentence_history.append((text, current_time))
            if len(_sentence_history) > 5:
                _sentence_history.pop(0)
            
            # Clear all pending partials (fresh start for next sentence)
            _pending_partials.clear()
            
            # Send final callback
            if _on_mic_text_callback:
                _on_mic_text_callback(text, is_final=True)
                logger.info(f"🎤 Mic final: {text}")
    
    def session_stopped_handler(evt):
        global _mic_active
        logger.warning("🎤 Mic session stopped")
        _mic_active = False
        
        # Auto-restart
        threading.Thread(target=_recover_mic, daemon=True).start()
    
    def canceled_handler(evt):
        logger.warning(f"🎤 Mic recognition canceled: {evt.reason}")
        threading.Thread(target=_recover_mic, daemon=True).start()
    
    def session_started_handler(evt):
        logger.info("✅ Mic session started")
    
    recognizer.recognizing.connect(recognizing_handler)
    recognizer.recognized.connect(recognized_handler)
    recognizer.session_stopped.connect(session_stopped_handler)
    recognizer.canceled.connect(canceled_handler)
    recognizer.session_started.connect(session_started_handler)

def _recover_mic():
    """Recover microphone"""
    global _mic_recognizer, _mic_active, _last_final_text, _partial_buffer, _pending_partials, _sentence_history
    
    logger.info("🔄 Recovering microphone...")
    time.sleep(2.0)
    
    try:
        if _mic_recognizer:
            try:
                _mic_recognizer.stop_continuous_recognition()
            except:
                pass
        
        # 🔥 RESET ALL TRACKING VARIABLES
        _last_final_text = ""
        _partial_buffer = ""
        _pending_partials.clear()
        _sentence_history.clear()
        
        recognizer = _create_mic_recognizer()
        if not recognizer:
            raise Exception("Failed to create recognizer")
        
        _setup_mic_handlers(recognizer)
        recognizer.start_continuous_recognition()
        
        _mic_recognizer = recognizer
        _mic_active = True
        
        logger.info("✅ Microphone recovered")
        
    except Exception as e:
        logger.error(f"❌ Mic recovery failed: {e}")
        threading.Timer(5.0, _recover_mic).start()

def start_mic_stt(callback=None):
    """Start microphone STT with callback - FIXED"""
    global _mic_recognizer, _mic_active, _on_mic_text_callback
    global _last_final_text, _partial_buffer, _pending_partials, _sentence_history
    
    # Store callback
    _on_mic_text_callback = callback
    
    # 🔥 RESET ALL TRACKING VARIABLES
    _last_final_text = ""
    _partial_buffer = ""
    _pending_partials.clear()
    _sentence_history.clear()
    
    logger.info("🎤 Starting microphone STT...")
    
    try:
        recognizer = _create_mic_recognizer()
        if not recognizer:
            raise Exception("Failed to create mic recognizer")
        
        _setup_mic_handlers(recognizer)
        recognizer.start_continuous_recognition()
        
        _mic_recognizer = recognizer
        _mic_active = True
        
        logger.info("✅ Mic STT started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start mic STT: {e}")
        threading.Timer(5.0, lambda: start_mic_stt(callback)).start()

def stop_mic_stt():
    """Stop microphone STT"""
    global _mic_recognizer, _mic_active, _last_final_text, _partial_buffer, _pending_partials, _sentence_history
    
    # 🔥 RESET ALL TRACKING VARIABLES
    _last_final_text = ""
    _partial_buffer = ""
    _pending_partials.clear()
    _sentence_history.clear()
    
    if _mic_recognizer:
        try:
            _mic_recognizer.stop_continuous_recognition()
            _mic_active = False
            logger.info("✅ Mic STT stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping mic: {e}")

def get_mic_status():
    """Get microphone status"""
    return {
        "active": _mic_active,
        "recognizer_exists": _mic_recognizer is not None,
        "last_final_text": _last_final_text,
        "partial_buffer": _partial_buffer,
        "pending_partials_count": len(_pending_partials),
        "sentence_history_count": len(_sentence_history)
    }