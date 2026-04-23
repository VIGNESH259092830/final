# app/shared/__init__.py
from .state import state

# Optional: Add these if they exist in your state.py
# from .state import set_speech_config, get_speech_config

# Or just export state
__all__ = ['state']