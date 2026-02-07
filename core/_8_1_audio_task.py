import datetime
import re
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from core.prompts import get_subtitle_trim_prompt, get_batch_subtitle_trim_prompt
from core.tts_backend.estimate_duration import init_estimator, estimate_duration
from core.utils import *
from core.utils.models import *

console = Console()
speed_factor = load_key("speed_factor")

TRANS_SUBS_FOR_AUDIO_FILE = 'output/audio/trans_subs_for_audio.srt'
SRC_SUBS_FOR_AUDIO_FILE = 'output/audio/src_subs_for_audio.srt'
ESTIMATOR = None

def batch_trim_subtitles(batches, retry_attempt=0):
    """Shorten multiple subtitles in a batch using GPT."""
    if not batches:
        return {}
    
    # Take duration from the first item since they should use same logic
    duration_limit = batches[0]['duration'] 
    prompt = get_batch_subtitle_trim_prompt(batches, duration_limit)
    
    def valid_batch_trim(response):
        for item in batches:
            if str(item['id']) not in response:
                return {'status': 'error', 'message': f'Missing ID {item["id"]} in response'}
        return {'status': 'success', 'message': ''}
    
    try:
        response = ask_gpt(prompt + " " * retry_attempt, resp_type='json', log_title='batch_sub_trim', valid_def=valid_batch_trim)
        return response
    except Exception as e:
        rprint(f"[bold red]Batch trimming failed: {e}, falling back to manual punctuation removal[/bold red]")
        fallback_results = {}
        for item in batches:
            fallback_results[str(item['id'])] = re.sub(r'[,.!?;:，。！？；：]', ' ', item['text']).strip()
        return fallback_results

def check_len_then_trim(text, duration):
    """Check if a subtitle needs trimming. (Maintained for backward compatibility but prefers batching)"""
    global ESTIMATOR
    if ESTIMATOR is None:
        ESTIMATOR = init_estimator()
    estimated_duration = estimate_duration(text, ESTIMATOR) / speed_factor['max']
    
    if estimated_duration > duration:
        return True, estimated_duration
    return False, estimated_duration

def time_diff_seconds(t1, t2, base_date):
    """Calculate the difference in seconds between two time objects"""
    dt1 = datetime.datetime.combine(base_date, t1)
    dt2 = datetime.datetime.combine(base_date, t2)
    return (dt2 - dt1).total_seconds()

def process_srt():
    """Process aligned Excel file, generate audio tasks"""
    df_aligned = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    
    subtitles = []
    for i, row in df_aligned.iterrows():
        try:
            # Parse number (1-based)
            number = i + 1
            
            # Parse timestamp string "HH:MM:SS,mmm --> HH:MM:SS,mmm"
            ts_start, ts_end = row['timestamp'].split(' --> ')
            start_time = datetime.datetime.strptime(ts_start, '%H:%M:%S,%f').time()
            end_time = datetime.datetime.strptime(ts_end, '%H:%M:%S,%f').time()
            
            duration = row['duration']
            text = str(row['Translation']).strip()
            # Remove content within parentheses
            text = re.sub(r'\([^)]*\)', '', text).strip()
            text = re.sub(r'（[^）]*）', '', text).strip()
            text = text.replace('-', '')
            
            origin = str(row['Source']).strip()
            speaker_id = row.get('speaker_id', None)

        except Exception as e:
            rprint(Panel(f"Unable to parse row {i}, error: {str(e)}, skipping.", title="Error", border_style="red"))
            continue
        
        subtitles.append({
            'number': number, 
            'start_time': start_time, 
            'end_time': end_time, 
            'duration': duration, 
            'text': text, 
            'origin': origin,
            'speaker_id': speaker_id
        })
    
    df = pd.DataFrame(subtitles)
    
    i = 0
    MIN_SUB_DUR = load_key("min_subtitle_duration")
    while i < len(df):
        today = datetime.date.today()
        # Merge criteria: 
        # 1. Duration < MIN_SUB_DUR
        # 2. Next segment starts soon
        # 3. SAME SPEAKER (Crucial for Diarization!)
        if df.loc[i, 'duration'] < MIN_SUB_DUR:
            # Handle NaN comparison: pd.isna handles both None and NaN
            speaker_i = df.loc[i, 'speaker_id']
            speaker_next = df.loc[i+1, 'speaker_id'] if i < len(df) - 1 else None
            same_speaker = (pd.isna(speaker_i) and pd.isna(speaker_next)) or (speaker_i == speaker_next)
            
            can_merge = (
                i < len(df) - 1 and 
                time_diff_seconds(df.loc[i, 'start_time'], df.loc[i+1, 'start_time'], today) < MIN_SUB_DUR and
                same_speaker
            )
            
            if can_merge:
                rprint(f"[bold yellow]Merging subtitles {i+1} and {i+2} (Speaker: {df.loc[i, 'speaker_id']})[/bold yellow]")
                df.loc[i, 'text'] += ' ' + df.loc[i+1, 'text']
                df.loc[i, 'origin'] += ' ' + df.loc[i+1, 'origin']
                df.loc[i, 'end_time'] = df.loc[i+1, 'end_time']
                df.loc[i, 'duration'] = time_diff_seconds(df.loc[i, 'start_time'], df.loc[i, 'end_time'], today)
                df = df.drop(i+1).reset_index(drop=True)
            else:
                if i < len(df) - 1:  # Not the last audio, but can't merge (diff speaker or too far)
                    rprint(f"[bold blue]Extending subtitle {i+1} duration to {MIN_SUB_DUR} seconds[/bold blue]")
                    df.loc[i, 'end_time'] = (datetime.datetime.combine(today, df.loc[i, 'start_time']) + 
                                            datetime.timedelta(seconds=MIN_SUB_DUR)).time()
                    df.loc[i, 'duration'] = MIN_SUB_DUR
                else:
                    rprint(f"[bold red]The last subtitle {i+1} duration is less than {MIN_SUB_DUR} seconds, but not extending[/bold red]")
                i += 1
        else:
            i += 1
    
    df['start_time'] = df['start_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])
    df['end_time'] = df['end_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])

    return df

@check_file_exists(_8_1_AUDIO_TASK)
def gen_audio_task_main():
    df = process_srt()
    console.print(df)
    df.to_excel(_8_1_AUDIO_TASK, index=False)
    rprint(Panel(f"Successfully generated {_8_1_AUDIO_TASK}", title="Success", border_style="green"))

if __name__ == '__main__':
    gen_audio_task_main()