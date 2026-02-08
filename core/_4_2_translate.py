import pandas as pd
import json
import concurrent.futures
from core.translate_lines import translate_lines
from core._4_1_summarize import search_things_to_note_in_prompt
from core._8_1_audio_task import check_len_then_trim
from core._6_gen_sub import align_timestamp
from core.utils import *
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from difflib import SequenceMatcher
from core.utils.models import *
console = Console()

# Function to split text into chunks
def split_chunks_by_chars(chunk_size, max_i): 
    """Split text into chunks based on character count, return list of (chunk_id, chunk_data) tuples
    
    Returns:
        List of tuples: (chunk_index, list of {'id': row_idx, 'text': text, 'speaker_id': speaker_id})
    """
    df = pd.read_excel(_3_2_SPLIT_BY_MEANING)
    sentences_data = df.to_dict('records')

    chunks = []
    chunk = []
    current_char_count = 0
    sentence_count = 0
    
    for row_idx, item in enumerate(sentences_data):
        sentence = str(item['text'])
        speaker_id = item.get('speaker_id', None)
        
        # Prefix with speaker for context (only for translation input, not stored)
        prefix = f"[{speaker_id}]: " if speaker_id is not None else ""
        labeled_sentence = prefix + sentence
        
        sentence_data = {
            'id': row_idx,  # 唯一 ID，用于关联
            'text': sentence,
            'speaker_id': speaker_id,
            'start': item.get('start'),
            'end': item.get('end'),
            'labeled_text': labeled_sentence  # 带 speaker 前缀的文本，用于翻译
        }
        
        if current_char_count + len(labeled_sentence + '\n') > chunk_size or sentence_count == max_i:
            chunks.append((len(chunks), chunk))
            chunk = [sentence_data]
            current_char_count = len(labeled_sentence + '\n')
            sentence_count = 1
        else:
            chunk.append(sentence_data)
            current_char_count += len(labeled_sentence + '\n')
            sentence_count += 1
    if chunk:
        chunks.append((len(chunks), chunk))
    return chunks

# Get context from surrounding chunks
def get_previous_content(chunks, chunk_index):
    if chunk_index == 0: return None
    # chunks is now list of (index, list of sentence_data)
    prev_chunk_data = chunks[chunk_index - 1][1]
    return [item['labeled_text'] for item in prev_chunk_data[-3:]]

def get_after_content(chunks, chunk_index):
    if chunk_index == len(chunks) - 1: return None
    next_chunk_data = chunks[chunk_index + 1][1]
    return [item['labeled_text'] for item in next_chunk_data[:2]]

# 🔍 Translate a single chunk
def translate_chunk(chunk_data, chunks, theme_prompt, i):
    """
    Translate a chunk of sentences.
    
    Args:
        chunk_data: Tuple of (chunk_index, list of sentence_data dicts)
    
    Returns:
        Tuple of (chunk_index, list of result dicts with id, translation, speaker_id)
    """
    chunk_idx, sentences = chunk_data
    things_to_note_prompt = search_things_to_note_in_prompt("\n".join([s['labeled_text'] for s in sentences]))
    previous_content_prompt = get_previous_content(chunks, i)
    after_content_prompt = get_after_content(chunks, i)
    
    # translate_lines now accepts list of dicts and returns list of result dicts
    result_list = translate_lines(sentences, previous_content_prompt, after_content_prompt, things_to_note_prompt, theme_prompt, i)
    return i, result_list

# Add similarity calculation function
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# 🚀 Main function to translate all chunks
@check_file_exists(_4_2_TRANSLATION)
def translate_all():
    # Increase chunk size to 1000 characters and max sentences per chunk to 20
    chunks = split_chunks_by_chars(chunk_size=1000, max_i=20)
    with open(_4_1_TERMINOLOGY, 'r', encoding='utf-8') as file:
        theme_prompt = json.load(file).get('theme')

    # 🔄 Use concurrent execution for translation
    # Create a fresh console for the progress bar to avoid "Only one live display" error
    # triggered by potential conflicts with global console instances in Streamlit environment.
    progress_console = Console()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True, console=progress_console) as progress:
        task = progress.add_task("[cyan]Translating chunks...", total=len(chunks))
        with concurrent.futures.ThreadPoolExecutor(max_workers=load_key("max_workers")) as executor:
            futures = []
            for i, chunk_data in enumerate(chunks):
                future = executor.submit(translate_chunk, chunk_data, chunks, theme_prompt, i)
                futures.append(future)
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                progress.update(task, advance=1)

    results.sort(key=lambda x: x[0])  # Sort results based on original order
    
    # 💾 Collect all translated results with IDs
    # results is a list of (chunk_index, list of result_dicts)
    all_results = []
    for chunk_idx, result_list in results:
        all_results.extend(result_list)
    
    # Sort by ID to maintain original order
    all_results.sort(key=lambda x: x['id'])
    
    # Build DataFrame with ID-based association
    src_text, trans_text, speaker_ids, starts, ends = [], [], [], [], []
    for item in all_results:
        src_text.append(item['text'])
        trans_text.append(item['translation'])
        speaker_ids.append(item['speaker_id'])
        starts.append(item.get('start'))
        ends.append(item.get('end'))
    
    # Trim long translation text
    df_text = pd.read_excel(_2_CLEANED_CHUNKS)
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.DataFrame({
        'Source': src_text, 
        'Translation': trans_text, 
        'speaker_id': speaker_ids,
        'start': starts,
        'end': ends
    })
    subtitle_output_configs = [('trans_subs_for_audio.srt', ['Translation'])]
    df_time = align_timestamp(df_text, df_translate, subtitle_output_configs, output_dir=None, for_display=False)
    
    # --- Batched Trimming Logic ---
    from core._8_1_audio_task import batch_trim_subtitles
    min_trim_duration = load_key("min_trim_duration")
    
    to_trim = []
    for idx, row in df_time.iterrows():
        if row['duration'] > min_trim_duration:
            needs_trim, est_dur = check_len_then_trim(row['Translation'], row['duration'])
            if needs_trim:
                to_trim.append({'id': idx, 'text': row['Translation'], 'duration': row['duration']})
    
    if to_trim:
        console.print(f"[yellow]Found {len(to_trim)} subtitles needing trimming. Processing in batches...[/yellow]")
        # Process in batches of 10
        batch_size = 10
        for i in range(0, len(to_trim), batch_size):
            batch = to_trim[i:i+batch_size]
            trimmed_results = batch_trim_subtitles(batch)
            for tid, ttext in trimmed_results.items():
                df_time.at[int(tid), 'Translation'] = ttext
        console.print("[green]✅ Batched trimming completed.[/green]")
    
    console.print(df_time)
    
    df_time.to_excel(_4_2_TRANSLATION, index=False)
    console.print("[bold green]✅ Translation completed and results saved.[/bold green]")

if __name__ == '__main__':
    translate_all()