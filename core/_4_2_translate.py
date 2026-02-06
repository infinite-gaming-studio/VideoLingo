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
    """Split text into chunks based on character count, return a list of multi-line text chunks"""
    df = pd.read_excel(_3_2_SPLIT_BY_MEANING)
    sentences_data = df.to_dict('records')

    chunks = []
    chunk = []
    current_char_count = 0
    sentence_count = 0
    for item in sentences_data:
        sentence = str(item['text'])
        speaker_id = item.get('speaker_id', None)
        # Prefix with speaker for context
        prefix = f"[{speaker_id}]: " if speaker_id is not None else ""
        labeled_sentence = prefix + sentence
        
        if current_char_count + len(labeled_sentence + '\n') > chunk_size or sentence_count == max_i:
            chunks.append("\n".join(chunk))
            chunk = [labeled_sentence]
            current_char_count = len(labeled_sentence + '\n')
            sentence_count = 1
        else:
            chunk.append(labeled_sentence)
            current_char_count += len(labeled_sentence + '\n')
            sentence_count += 1
    if chunk:
        chunks.append("\n".join(chunk))
    return chunks

# Get context from surrounding chunks
def get_previous_content(chunks, chunk_index):
    if chunk_index == 0: return None
    lines = chunks[chunk_index - 1].split('\n')
    return lines[-3:] # Get last 3 lines
def get_after_content(chunks, chunk_index):
    if chunk_index == len(chunks) - 1: return None
    lines = chunks[chunk_index + 1].split('\n')
    return lines[:2] # Get first 2 lines

# 🔍 Translate a single chunk
def translate_chunk(chunk, chunks, theme_prompt, i):
    things_to_note_prompt = search_things_to_note_in_prompt(chunk)
    previous_content_prompt = get_previous_content(chunks, i)
    after_content_prompt = get_after_content(chunks, i)
    # translate_lines expects strings
    translation, original_with_speakers = translate_lines(chunk, previous_content_prompt, after_content_prompt, things_to_note_prompt, theme_prompt, i)
    return i, original_with_speakers, translation

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
            for i, chunk in enumerate(chunks):
                future = executor.submit(translate_chunk, chunk, chunks, theme_prompt, i)
                futures.append(future)
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                progress.update(task, advance=1)

    results.sort(key=lambda x: x[0])  # Sort results based on original order
    
    # 💾 Save results to lists and Excel file
    src_text, trans_text, speaker_ids = [], [], []
    df_source = pd.read_excel(_3_2_SPLIT_BY_MEANING)
    
    # Reconstruct src_text and trans_text from results
    # results is a list of (index, original_with_speakers, translation)
    total_lines = 0
    for i, chunk_str in enumerate(chunks):
        chunk_results = [r for r in results if r[0] == i][0]
        original_lines = chunk_results[1].split('\n')
        translated_lines = chunk_results[2].split('\n')
        
        for orig, trans in zip(original_lines, translated_lines):
            # Strip speaker prefix from orig for saving if needed, but we already have df_source
            src_text.append(df_source.iloc[total_lines]['text'])
            speaker_ids.append(df_source.iloc[total_lines]['speaker_id'])
            trans_text.append(trans)
            total_lines += 1
    
    # Trim long translation text
    df_text = pd.read_excel(_2_CLEANED_CHUNKS)
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.DataFrame({'Source': src_text, 'Translation': trans_text, 'speaker_id': speaker_ids})
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