import os
import pandas as pd
import subprocess
from core.utils.models import _6_ALIGNED_FOR_AUDIO, _VOCAL_AUDIO_FILE, _AUDIO_REFERS_DIR
from core.utils.config_utils import load_key, update_key
from core.prompts import ask_gpt

def extract_speaker_snippets():
    """Extract a 3-5s snippet for each unique speaker from the vocal audio file."""
    if not os.path.exists(_6_ALIGNED_FOR_AUDIO) or not os.path.exists(_VOCAL_AUDIO_FILE):
        return
    
    os.makedirs(_AUDIO_REFERS_DIR, exist_ok=True)
    df = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    
    if 'speaker_id' not in df.columns:
        return

    unique_speakers = df['speaker_id'].dropna().unique()
    
    for speaker in unique_speakers:
        output_path = os.path.join(_AUDIO_REFERS_DIR, f"{speaker}.mp3")
        if os.path.exists(output_path):
            continue
            
        # Find the first occurrence with sufficient duration
        sample_row = df[df['speaker_id'] == speaker].iloc[0]
        start_time = sample_row['timestamp'].split(' --> ')[0].replace(',', '.')
        
        # Extract 3 seconds using ffmpeg
        cmd = [
            'ffmpeg', '-y', '-ss', start_time, '-t', '3', 
            '-i', _VOCAL_AUDIO_FILE, '-acodec', 'libmp3lame', output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

from core.prompts import ask_gpt, get_speaker_profile_prompt

_SPEAKER_MAPPINGS_FILE = "output/log/speaker_mappings.json"

def get_voice_list(tts_method):
    """Return a list of common voices for the selected TTS method."""
    if tts_method == 'edge_tts':
        return ['en-US-JennyNeural', 'en-US-GuyNeural', 'en-GB-SoniaNeural', 'en-GB-RyanNeural', 'zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural']
    elif tts_method == 'openai_tts':
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    # Add more as needed
    return []

def get_speaker_profiles():
    """Analyze speaker dialogue using GPT to suggest gender and tone."""
    if not os.path.exists(_6_ALIGNED_FOR_AUDIO):
        return {}
        
    df = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    if 'speaker_id' not in df.columns:
        return {}

    speaker_texts = df.groupby('speaker_id')['Translation'].apply(lambda x: " ".join(map(str, x[:10]))).to_dict()
    tts_method = load_key("tts_method")
    
    profiles = {}
    for speaker, text in speaker_texts.items():
        prompt = get_speaker_profile_prompt(speaker, text, tts_method)
        try:
            res = ask_gpt(prompt, response_json=True, log_title=f"profile_{speaker}")
            profiles[speaker] = res
        except Exception as e:
            print(f"Error profiling {speaker}: {e}")
            profiles[speaker] = {"gender": "Unknown", "tone": "N/A", "age": "N/A", "recommended_voice": ""}
            
    return profiles

def save_speaker_mappings(mappings):
    """Save user-confirmed speaker-to-voice mappings."""
    import json
    with open(_SPEAKER_MAPPINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)

def load_speaker_mappings():
    """Load speaker-to-voice mappings."""
    import json
    if os.path.exists(_SPEAKER_MAPPINGS_FILE):
        with open(_SPEAKER_MAPPINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

if __name__ == "__main__":
    extract_speaker_snippets()
    print(get_speaker_profiles())
