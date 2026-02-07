import os
import pandas as pd
import subprocess
from core.utils.models import _6_ALIGNED_FOR_AUDIO, _VOCAL_AUDIO_FILE, _AUDIO_REFERS_DIR
from core.utils.config_utils import load_key, update_key
from core.prompts import ask_gpt

def extract_speaker_snippets():
    """Extract a 3-5s snippet for each unique speaker from the vocal audio file."""
    if not os.path.exists(_6_ALIGNED_FOR_AUDIO) or not os.path.exists(_VOCAL_AUDIO_FILE):
        print("[yellow]⚠️ Cannot extract speaker snippets: aligned file or vocal audio not found[/yellow]")
        return
    
    os.makedirs(_AUDIO_REFERS_DIR, exist_ok=True)
    try:
        df = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    except Exception as e:
        print(f"[red]❌ Error reading aligned file: {e}[/red]")
        return
    
    if 'speaker_id' not in df.columns:
        print("[yellow]⚠️ No speaker_id column found, skipping snippet extraction[/yellow]")
        return

    unique_speakers = df['speaker_id'].dropna().unique()
    print(f"[cyan]🎵 Extracting audio snippets for {len(unique_speakers)} speakers...[/cyan]")
    
    for speaker in unique_speakers:
        output_path = os.path.join(_AUDIO_REFERS_DIR, f"{speaker}.mp3")
        if os.path.exists(output_path):
            continue
            
        try:
            # Find the first occurrence with sufficient duration
            sample_row = df[df['speaker_id'] == speaker].iloc[0]
            start_time = sample_row['timestamp'].split(' --> ')[0].replace(',', '.')
            
            # Extract 3 seconds using ffmpeg
            cmd = [
                'ffmpeg', '-y', '-ss', start_time, '-t', '3', 
                '-i', _VOCAL_AUDIO_FILE, '-acodec', 'libmp3lame', output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[green]✅ Extracted snippet for {speaker}[/green]")
            else:
                print(f"[yellow]⚠️ Failed to extract snippet for {speaker}: {result.stderr[:100]}[/yellow]")
        except Exception as e:
            print(f"[red]❌ Error extracting snippet for {speaker}: {e}[/red]")
    
    print(f"[green]✅ Speaker snippets saved to {_AUDIO_REFERS_DIR}[/green]")

from core.prompts import ask_gpt, get_speaker_profile_prompt

_SPEAKER_MAPPINGS_FILE = "output/log/speaker_mappings.json"

def get_voice_list(tts_method):
    """Return a list of common voices for the selected TTS method."""
    voice_lists = {
        'edge_tts': [
            # English
            'en-US-JennyNeural', 'en-US-GuyNeural', 'en-US-AnaNeural',
            'en-GB-SoniaNeural', 'en-GB-RyanNeural', 'en-GB-LibbyNeural',
            'en-AU-NatashaNeural', 'en-AU-WilliamNeural',
            # Chinese
            'zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural', 'zh-CN-YunjianNeural',
            'zh-CN-XiaoyiNeural', 'zh-HK-HiuMaanNeural', 'zh-HK-HiuGaaiNeural',
            'zh-HK-WanLungNeural', 'zh-TW-HsiaoChenNeural', 'zh-TW-HsiaoYuNeural',
            # Japanese
            'ja-JP-NanamiNeural', 'ja-JP-KeitaNeural',
            # Korean
            'ko-KR-SunHiNeural', 'ko-KR-InJoonNeural',
            # European
            'de-DE-KatjaNeural', 'de-DE-ConradNeural',
            'fr-FR-DeniseNeural', 'fr-FR-HenriNeural',
            'es-ES-ElviraNeural', 'es-ES-AlvaroNeural',
            'it-IT-ElsaNeural', 'it-IT-DiegoNeural',
            'ru-RU-SvetlanaNeural', 'ru-RU-DmitryNeural',
        ],
        'openai_tts': ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        'azure_tts': [
            'en-US-JennyNeural', 'en-US-GuyNeural',
            'zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural',
            'ja-JP-NanamiNeural', 'ko-KR-SunHiNeural',
        ],
        'gpt_sovits': ['Default'],  # GPT-SoVITS uses reference audio, not voice IDs
        'f5_tts': ['Default'],  # F5-TTS uses reference audio
        'fish_tts': ['Default'],  # Fish TTS uses reference audio
        'custom_tts': ['Default'],  # Custom TTS defined by user
    }
    return voice_lists.get(tts_method, [])

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
