"""German text to speech with multilingual Chatterbox, locally on Apple Silicon (mlx-audio). Day 1 TTS slide."""
from mlx_audio.tts.generate import generate_audio

generate_audio(
    text="Guten Tag!",
    model="mlx-community/chatterbox-fp16",   # the multilingual model
    lang_code="de",
    file_prefix="guten_tag",
    audio_format="wav",
    play=True,
)
