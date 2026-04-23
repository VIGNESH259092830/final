# app/audio/system_stt.py - COMPLETE WORKING VERSION WITH DUPLICATE PREVENTION
import soundcard as sc
import numpy as np
import azure.cognitiveservices.speech as speechsdk
import threading
import time
import logging
import traceback
from app.shared import state

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= CONFIGURATION =================
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 0.0001
DEVICE_CHECK_INTERVAL = 5.0
KEEP_ALIVE_INTERVAL = 5.0
MIN_AUDIO_LEVEL = 0.00001

# ================= GLOBAL STATE =================
_system_recognizer = None
_system_stream = None
_system_active = False
_system_audio_thread = None
_stop_system_audio = False
_system_lock = threading.RLock()
_current_speaker = None
_last_audio_time = time.time()
_device_recovery_count = 0
_health_monitor_thread = None
_is_streaming = False
_recognizer_ready = False
_stream_closed = False
_forced_restart = False

# 🔥 NEW: Duplicate prevention for system audio
_system_last_final_text = ""
_system_partial_buffer = ""
_system_last_partial_time = 0
_system_final_history = []
_system_partial_history = []
_system_processing_lock = threading.RLock()

# ================= SPEECH RECOGNIZER =================
def _create_speech_recognizer():
    """Create a persistent speech recognizer with proper timeouts"""
    global _recognizer_ready, _stream_closed
    
    try:
        _stream_closed = False
        
        stream_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=SAMPLE_RATE,
            bits_per_sample=16,
            channels=2
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
        
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        
        if not state.speech_config:
            raise ValueError("No speech configuration available")
        
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=state.speech_config,
            audio_config=audio_config
        )
        
        recognizer.properties.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "15000"
        )
        
        recognizer.properties.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            "1000"
        )
        
        logger.info("✅ Speech recognizer created with 15s/1s timeouts")
        _recognizer_ready = True
        
        return recognizer, push_stream
        
    except Exception as e:
        logger.error(f"❌ Failed to create recognizer: {e}")
        _recognizer_ready = False
        raise e

# ================= DEVICE MANAGEMENT =================
def _find_best_speaker():
    """Find the best available speaker device"""
    try:
        speaker = sc.default_speaker()
        if speaker:
            return speaker
        
        speakers = sc.all_speakers()
        if speakers:
            return speakers[0]
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Error finding speaker: {e}")
        return None

def _setup_loopback_microphone(speaker):
    """Setup loopback microphone for a speaker"""
    try:
        if not speaker:
            return None
        
        # Try different methods
        methods = [
            lambda: sc.get_microphone(id=str(speaker.id), include_loopback=True),
            lambda: sc.get_microphone(id=speaker.name, include_loopback=True),
            lambda: sc.default_microphone(include_loopback=True),
            lambda: next((m for m in sc.all_microphones(include_loopback=True) 
                         if "loopback" in m.name.lower()), None)
        ]
        
        for method in methods:
            try:
                mic = method()
                if mic:
                    logger.info(f"✅ Found loopback: {mic.name}")
                    return mic
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Loopback setup failed: {e}")
        return None

# ================= DUPLICATE PREVENTION =================
def _is_system_duplicate(text, is_final, current_time):
    """Check if system audio text is a duplicate"""
    global _system_last_final_text, _system_partial_buffer, _system_last_partial_time
    global _system_final_history, _system_partial_history
    
    with _system_processing_lock:
        if is_final:
            # Skip if same as last final text within 50ms
            if text == _system_last_final_text and (current_time - _system_last_partial_time) < 0.05:
                return True
            
            # Skip if in recent history
            if text in _system_final_history:
                return True
            
            # Check for punctuation variations
            import re
            clean_text = re.sub(r'[.,;!?]+$', '', text)
            for history_text in _system_final_history:
                clean_history = re.sub(r'[.,;!?]+$', '', history_text)
                if clean_text == clean_history:
                    return True
            
            # Add to history (keep last 5)
            _system_final_history.append(text)
            if len(_system_final_history) > 5:
                _system_final_history.pop(0)
            
            _system_last_final_text = text
            
        else:
            # For partial text
            # Skip if same partial within 30ms
            if text == _system_partial_buffer and (current_time - _system_last_partial_time) < 0.03:
                return True
            
            # Skip if partial is contained in last final text
            if _system_last_final_text and text in _system_last_final_text:
                return True
            
            # Skip if in recent partial history
            if text in _system_partial_history:
                return True
            
            # Update tracking
            _system_partial_buffer = text
            _system_last_partial_time = current_time
            
            # Add to history (keep last 3)
            _system_partial_history.append(text)
            if len(_system_partial_history) > 3:
                _system_partial_history.pop(0)
        
        return False

def _clean_system_text(text):
    """Clean system audio text"""
    import re
    
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

# ================= AUDIO CAPTURE ENGINE =================
def _audio_capture_engine():
    """Main audio capture engine"""
    global _current_speaker, _last_audio_time, _device_recovery_count, _is_streaming
    global _stream_closed, _forced_restart
    
    logger.info("🚀 Starting audio capture engine...")
    
    while not _stop_system_audio:
        try:
            speaker = _find_best_speaker()
            if not speaker:
                time.sleep(2.0)
                continue
            
            _current_speaker = speaker
            
            mic = _setup_loopback_microphone(speaker)
            if not mic:
                time.sleep(3.0)
                continue
            
            logger.info(f"🎧 Capturing from: {speaker.name}")
            
            with mic.recorder(samplerate=SAMPLE_RATE, channels=2) as recorder:
                _is_streaming = True
                _stream_closed = False
                logger.info("✅ Audio stream started")
                
                while not _stop_system_audio and _is_streaming:
                    try:
                        # Capture audio
                        try:
                            audio_data = recorder.record(numframes=CHUNK_SIZE)
                        except Exception as e:
                            logger.error(f"🎤 Capture error: {e}")
                            time.sleep(0.1)
                            continue
                        
                        if audio_data is None or len(audio_data) == 0:
                            audio_data = np.zeros((CHUNK_SIZE, 2), dtype=np.float32)
                        
                        # Check audio level
                        audio_level = float(np.abs(audio_data).mean())
                        
                        if audio_level > MIN_AUDIO_LEVEL:
                            _last_audio_time = time.time()
                        
                        # Convert and send
                        pcm_audio = np.clip(audio_data, -1.0, 1.0)
                        pcm_audio = (pcm_audio * 32767).astype(np.int16)
                        
                        if _system_stream and not _stream_closed:
                            try:
                                _system_stream.write(pcm_audio.tobytes())
                            except Exception as e:
                                logger.error(f"❌ Stream write failed: {e}")
                                _stream_closed = True
                                break
                        
                        time.sleep(0.001)
                        
                    except Exception as e:
                        logger.error(f"🎧 Inner capture error: {e}")
                        time.sleep(0.1)
                        break
                
                _is_streaming = False
                
                if not _stop_system_audio and _stream_closed:
                    logger.info("🔄 Stream closed, restarting...")
                    _forced_restart = True
                    break
                
        except Exception as e:
            logger.error(f"🎧 Outer capture error: {e}")
            _is_streaming = False
            
            _device_recovery_count += 1
            if _device_recovery_count > 10:
                break
            
            wait_time = min(1.0 * (2 ** _device_recovery_count), 10.0)
            logger.info(f"🔄 Recovery attempt {_device_recovery_count} in {wait_time:.1f}s...")
            time.sleep(wait_time)
    
    logger.info("🎧 Audio capture engine stopped")

# ================= EVENT HANDLERS =================
def _setup_speech_handlers(recognizer, on_text):
    """Setup speech recognition event handlers - WITH DUPLICATE PREVENTION"""
    
    def recognizing_handler(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            text = evt.result.text.strip()
            if text and not state.mute_system:
                current_time = time.time()
                cleaned_text = _clean_system_text(text)
                
                # 🔥 CHECK FOR DUPLICATES
                if _is_system_duplicate(cleaned_text, is_final=False, current_time=current_time):
                    logger.debug(f"💻 Skipping duplicate system partial: {cleaned_text}")
                    return
                
                logger.info(f"💻 System (partial): {cleaned_text}")
                if on_text:
                    try:
                        on_text(cleaned_text, is_final=False)
                    except Exception as e:
                        logger.error(f"💻 Partial callback error: {e}")
    
    def recognized_handler(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text.strip()
            if text and not state.mute_system:
                current_time = time.time()
                cleaned_text = _clean_system_text(text)
                
                # 🔥 CHECK FOR DUPLICATES
                if _is_system_duplicate(cleaned_text, is_final=True, current_time=current_time):
                    logger.info(f"💻 Skipping duplicate system final: {cleaned_text}")
                    return
                
                logger.info(f"💻 System (final): {cleaned_text}")
                if on_text:
                    try:
                        on_text(cleaned_text, is_final=True)
                    except Exception as e:
                        logger.error(f"💻 Final callback error: {e}")
    
    def session_started_handler(evt):
        global _system_active, _recognizer_ready
        with _system_lock:
            _system_active = True
            _recognizer_ready = True
        logger.info("💻 Speech session STARTED")
    
    def session_stopped_handler(evt):
        global _system_active, _recognizer_ready
        with _system_lock:
            _system_active = False
            _recognizer_ready = False
        
        logger.warning(f"💻 Speech session STOPPED")
        
        if not state.mute_system and not _stop_system_audio:
            logger.info("🔄 Auto-restarting session in 1 second...")
            threading.Timer(1.0, _restart_speech_session, args=[on_text]).start()
    
    def canceled_handler(evt):
        if evt.reason == speechsdk.CancellationReason.Error:
            error_details = evt.error_details if hasattr(evt, 'error_details') else 'No details'
            logger.error(f"💻 Recognition ERROR: {error_details}")
            
            if not state.mute_system and not _stop_system_audio:
                logger.info("🔄 Auto-restarting after error in 2 seconds...")
                threading.Timer(2.0, _restart_speech_session, args=[on_text]).start()
    
    recognizer.recognizing.connect(recognizing_handler)
    recognizer.recognized.connect(recognized_handler)
    recognizer.session_started.connect(session_started_handler)
    recognizer.session_stopped.connect(session_stopped_handler)
    recognizer.canceled.connect(canceled_handler)

def _restart_speech_session(on_text):
    """Restart speech recognition session"""
    global _system_recognizer, _system_stream
    global _system_last_final_text, _system_partial_buffer, _system_final_history, _system_partial_history
    
    if state.mute_system or _stop_system_audio:
        return
    
    logger.info("🔧 Restarting speech session...")
    
    try:
        if _system_recognizer:
            try:
                _system_recognizer.stop_continuous_recognition()
            except:
                pass
        
        if _system_stream:
            try:
                _system_stream.close()
            except:
                pass
        
        # Reset duplicate tracking
        with _system_processing_lock:
            _system_last_final_text = ""
            _system_partial_buffer = ""
            _system_final_history.clear()
            _system_partial_history.clear()
        
        time.sleep(0.5)
        
        recognizer, stream = _create_speech_recognizer()
        _setup_speech_handlers(recognizer, on_text)
        
        _system_recognizer = recognizer
        _system_stream = stream
        
        recognizer.start_continuous_recognition()
        logger.info("✅ Speech session restarted")
        
    except Exception as e:
        logger.error(f"❌ Failed to restart speech: {e}")
        if not state.mute_system and not _stop_system_audio:
            threading.Timer(3.0, _restart_speech_session, args=[on_text]).start()

# ================= HEALTH MONITOR =================
def _health_monitor():
    """Monitor system audio health"""
    logger.info("❤️ Starting health monitor...")
    
    while not _stop_system_audio:
        try:
            time.sleep(10.0)
            
            with _system_lock:
                recognizer_alive = _system_recognizer is not None and _system_active
                capture_alive = _is_streaming
                time_since_audio = time.time() - _last_audio_time
            
            if not state.mute_system and not _stop_system_audio:
                if not recognizer_alive:
                    logger.warning(f"⚠️ Recognizer not alive")
                elif not capture_alive:
                    logger.warning(f"⚠️ Capture stopped")
                elif time_since_audio > 60.0:
                    logger.warning(f"⚠️ No audio for {time_since_audio:.0f}s")
            
        except Exception as e:
            logger.error(f"❤️ Health monitor error: {e}")
            time.sleep(10.0)
    
    logger.info("❤️ Health monitor stopped")

# ================= PUBLIC API =================
def start_system_stt(speech_config, on_text):
    """Start system audio STT"""
    global _system_recognizer, _system_stream, _system_active
    global _system_audio_thread, _stop_system_audio, _health_monitor_thread
    global _system_last_final_text, _system_partial_buffer, _system_final_history, _system_partial_history
    
    logger.info("🚀 Starting system audio STT...")
    
    _stop_system_audio = False
    
    try:
        state.speech_config = speech_config
        
        # Reset duplicate tracking
        with _system_processing_lock:
            _system_last_final_text = ""
            _system_partial_buffer = ""
            _system_final_history.clear()
            _system_partial_history.clear()
        
        recognizer, stream = _create_speech_recognizer()
        _setup_speech_handlers(recognizer, on_text)
        
        _system_recognizer = recognizer
        _system_stream = stream
        
        recognizer.start_continuous_recognition()
        
        with _system_lock:
            _system_active = True
        
        logger.info("✅ Speech recognizer started")
        
        if _system_audio_thread is None or not _system_audio_thread.is_alive():
            _system_audio_thread = threading.Thread(
                target=_audio_capture_engine,
                daemon=True,
                name="SystemAudioCapture"
            )
            _system_audio_thread.start()
            logger.info("✅ Audio capture engine started")
        
        if _health_monitor_thread is None or not _health_monitor_thread.is_alive():
            _health_monitor_thread = threading.Thread(
                target=_health_monitor,
                daemon=True,
                name="SystemHealthMonitor"
            )
            _health_monitor_thread.start()
            logger.info("✅ Health monitor started")
        
        return recognizer
        
    except Exception as e:
        logger.error(f"❌ Failed to start system STT: {e}")
        
        if not state.mute_system:
            logger.info("🔄 Auto-retry in 5 seconds...")
            threading.Timer(5.0, lambda: start_system_stt(speech_config, on_text)).start()
        
        raise e

def stop_system_recognition():
    """Stop system audio recognition"""
    global _system_recognizer, _system_stream, _system_active
    global _system_audio_thread, _stop_system_audio, _health_monitor_thread
    global _system_last_final_text, _system_partial_buffer, _system_final_history, _system_partial_history
    
    logger.info("🛑 Stopping system audio...")
    
    _stop_system_audio = True
    
    if _system_recognizer:
        try:
            _system_recognizer.stop_continuous_recognition()
        except:
            pass
        _system_recognizer = None
    
    if _system_stream:
        try:
            _system_stream.close()
        except:
            pass
        _system_stream = None
    
    # Reset duplicate tracking
    with _system_processing_lock:
        _system_last_final_text = ""
        _system_partial_buffer = ""
        _system_final_history.clear()
        _system_partial_history.clear()
    
    with _system_lock:
        _system_active = False
    
    logger.info("✅ System audio stopped")

def force_refresh():
    """Force refresh system audio"""
    if state.mute_system:
        return False
    
    logger.info("🔧 Force refreshing system audio...")
    
    global _system_recognizer
    if _system_recognizer:
        try:
            _system_recognizer.stop_continuous_recognition()
            logger.info("✅ Triggered refresh")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to trigger refresh: {e}")
    
    return False

def send_keepalive():
    """Manually send keep-alive packet - SIMPLIFIED"""
    try:
        if _system_stream and not _stream_closed:
            # Create silent audio
            silent_chunk = np.zeros((CHUNK_SIZE, 2), dtype=np.float32)
            silent_pcm = (silent_chunk * 32767).astype(np.int16).tobytes()
            _system_stream.write(silent_pcm)
            logger.debug("🔧 Keep-alive sent")
            return True
    except Exception as e:
        logger.warning(f"🔧 Keep-alive failed: {e}")
    
    return False

def test_system_audio():
    """Test if system audio is working"""
    try:
        speaker = _find_best_speaker()
        if speaker:
            return {"success": True, "speaker": speaker.name}
        else:
            return {"success": False, "error": "No speaker found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_system_status():
    """Get detailed system status"""
    with _system_lock:
        current_time = time.time()
        time_since_audio = current_time - _last_audio_time
        
        with _system_processing_lock:
            return {
                "active": _system_active,
                "recognizer_exists": _system_recognizer is not None,
                "capture_running": _is_streaming,
                "current_speaker": _current_speaker.name if _current_speaker else None,
                "muted": state.mute_system,
                "seconds_since_audio": time_since_audio,
                "recovery_count": _device_recovery_count,
                "stop_requested": _stop_system_audio,
                "stream_closed": _stream_closed,
                "last_final_text": _system_last_final_text,
                "partial_buffer": _system_partial_buffer,
                "final_history_count": len(_system_final_history),
                "partial_history_count": len(_system_partial_history),
                "timestamp": current_time
            }

# Simple test
if __name__ == "__main__":
    print("System Audio STT Module")
    print("Functions available:")
    print("- start_system_stt(speech_config, on_text)")
    print("- stop_system_recognition()")
    print("- get_system_status()")
    print("- force_refresh()")
    print("- send_keepalive()")
    print("- test_system_audio()")