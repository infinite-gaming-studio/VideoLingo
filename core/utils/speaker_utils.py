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
        # Skip if any reference already exists for this speaker
        output_path_mp3 = os.path.join(_AUDIO_REFERS_DIR, f"{speaker}.mp3")
        output_path_wav = os.path.join(_AUDIO_REFERS_DIR, f"{speaker}.wav")
        
        # Check if user has already provided a custom reference audio
        if os.path.exists(output_path_mp3) or os.path.exists(output_path_wav):
            print(f"[dim]⏭️ Skipping {speaker}: reference audio already exists[/dim]")
            continue

        try:
            # Find the first occurrence with sufficient duration
            sample_row = df[df['speaker_id'] == speaker].iloc[0]
            start_time = sample_row['timestamp'].split(' --> ')[0].replace(',', '.')

            # Extract 3 seconds using ffmpeg
            cmd = [
                'ffmpeg', '-y', '-ss', start_time, '-t', '3',
                '-i', _VOCAL_AUDIO_FILE, '-acodec', 'libmp3lame', output_path_mp3
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
        'indextts': ['Default'],  # IndexTTS uses reference audio for voice cloning
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
            res = ask_gpt(prompt, resp_type="json", log_title=f"profile_{speaker}")
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


def merge_speakers(df_aligned, speakers_to_merge):
    """Merge multiple speakers into one (the first one in the list).
    
    Args:
        df_aligned: DataFrame with aligned subtitles
        speakers_to_merge: List of speaker IDs to merge
    """
    if len(speakers_to_merge) < 2:
        return
    
    # Use the first speaker as the target
    target_speaker = speakers_to_merge[0]
    
    # Replace all speakers in the list with the target
    for speaker in speakers_to_merge[1:]:
        df_aligned.loc[df_aligned['speaker_id'] == speaker, 'speaker_id'] = target_speaker
    
    # Save the modified DataFrame
    df_aligned.to_excel(_6_ALIGNED_FOR_AUDIO, index=False)
    print(f"[green]✅ Merged {len(speakers_to_merge)} speakers into {target_speaker}[/green]")


def split_speaker_by_time(df_aligned, speaker_to_split, split_points):
    """Split a speaker into multiple speakers based on time points.
    
    Args:
        df_aligned: DataFrame with aligned subtitles
        speaker_to_split: Speaker ID to split
        split_points: List of time points (in seconds) to split at
    """
    if not split_points:
        return
    
    # Parse timestamps to seconds
    def parse_timestamp(ts_str):
        try:
            start_str = ts_str.split(' --> ')[0]
            parts = start_str.replace(',', '.').split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except:
            return 0
    
    # Add temporary column with start time in seconds
    df_aligned['start_sec'] = df_aligned['timestamp'].apply(parse_timestamp)
    
    # Sort split points
    split_points = sorted(split_points)
    
    # Create new speaker names
    base_name = speaker_to_split
    new_speaker_names = [f"{base_name}_PART{i+1}" for i in range(len(split_points) + 1)]
    
    # Update speaker IDs based on time ranges
    for idx, row in df_aligned.iterrows():
        if row['speaker_id'] == speaker_to_split:
            start_sec = row['start_sec']
            
            # Determine which segment this belongs to
            segment_idx = 0
            for split_point in split_points:
                if start_sec >= split_point:
                    segment_idx += 1
                else:
                    break
            
            df_aligned.at[idx, 'speaker_id'] = new_speaker_names[segment_idx]
    
    # Drop temporary column
    df_aligned.drop(columns=['start_sec'], inplace=True)
    
    # Save the modified DataFrame
    df_aligned.to_excel(_6_ALIGNED_FOR_AUDIO, index=False)
    print(f"[green]✅ Split {speaker_to_split} into {len(new_speaker_names)} speakers: {', '.join(new_speaker_names)}[/green]")


def reassign_speaker_segment(df_aligned, start_time, end_time, old_speaker, new_speaker):
    """Reassign a specific time segment from one speaker to another.
    
    Useful for fine-tuning when automatic detection is wrong for specific segments.
    
    Args:
        df_aligned: DataFrame with aligned subtitles
        start_time: Start time in seconds
        end_time: End time in seconds
        old_speaker: Current speaker ID
        new_speaker: New speaker ID to assign
    """
    def parse_timestamp(ts_str):
        try:
            start_str = ts_str.split(' --> ')[0]
            parts = start_str.replace(',', '.').split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except:
            return 0
    
    # Add temporary column with start time in seconds
    df_aligned['start_sec'] = df_aligned['timestamp'].apply(parse_timestamp)
    
    # Find segments within the time range and matching the old speaker
    mask = (
        (df_aligned['speaker_id'] == old_speaker) &
        (df_aligned['start_sec'] >= start_time) &
        (df_aligned['start_sec'] <= end_time)
    )
    
    count = mask.sum()
    df_aligned.loc[mask, 'speaker_id'] = new_speaker
    
    # Drop temporary column
    df_aligned.drop(columns=['start_sec'], inplace=True)
    
    # Save the modified DataFrame
    df_aligned.to_excel(_6_ALIGNED_FOR_AUDIO, index=False)
    print(f"[green]✅ Reassigned {count} segments from {old_speaker} to {new_speaker}[/green]")
    return count

if __name__ == "__main__":
    extract_speaker_snippets()
    print(get_speaker_profiles())
