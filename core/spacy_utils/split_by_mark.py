import os
import pandas as pd
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_MARK_FILE
from core.utils.config_utils import load_key, get_joiner
from rich import print as rprint

warnings.filterwarnings("ignore", category=FutureWarning)

def split_by_mark(nlp):
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language 
    joiner = get_joiner(language)
    rprint(f"[blue]🔍 Using {language} language joiner: '{joiner}'[/blue]")
    
    chunks = pd.read_excel("output/log/cleaned_chunks.xlsx")
    # Clean text and handle speaker_id
    chunks.text = chunks.text.apply(lambda x: str(x).strip('"').strip(""))
    # Keep None as None, don't convert to string 'None'
    if 'speaker_id' in chunks.columns:
        chunks['speaker_id'] = chunks['speaker_id'].where(chunks['speaker_id'].notna(), None)
    
    sentences_by_mark = []
    
    # 1. Group continuous chunks by speaker
    current_speaker = None
    group_text = ""
    group_words_info = [] # List of (char_start, char_end, word_start_time, word_end_time)
    
    for i, row in chunks.iterrows():
        text = str(row['text'])
        speaker = row['speaker_id']
        start_time = row['start']
        end_time = row['end']
        
        if speaker != current_speaker:
            # Process previous group
            if group_text:
                process_group(nlp, group_text, group_words_info, current_speaker, sentences_by_mark)
            
            # Reset for new group
            current_speaker = speaker
            group_text = text
            group_words_info = [(0, len(text), start_time, end_time)]
        else:
            # Same speaker, join
            group_text += joiner + text
            # Track character range for this word in the group_text
            start_char = len(group_text) - len(text)
            group_words_info.append((start_char, len(group_text), start_time, end_time))
            
    # Process last group
    if group_text:
        process_group(nlp, group_text, group_words_info, current_speaker, sentences_by_mark)

    # 2. Punctuation merging logic
    final_sentences = []
    for i, item in enumerate(sentences_by_mark):
        if i > 0 and item['text'].strip() in [',', '.', '，', '。', '？', '！'] and final_sentences:
            final_sentences[-1]['text'] += item['text'].strip()
            final_sentences[-1]['end'] = max(final_sentences[-1]['end'], item['end'])
        else:
            final_sentences.append(item)

    # Save to Excel
    df_output = pd.DataFrame(final_sentences)
    df_output.to_excel(SPLIT_BY_MARK_FILE, index=False)
    rprint(f"[green]💾 Sentences split by punctuation marks saved to →  `{SPLIT_BY_MARK_FILE}`[/green]")

def process_group(nlp, group_text, words_info, speaker, results_list):
    """Split a speaker's text group into sentences and map timestamps."""
    doc = nlp(group_text)
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue
            
        sent_start_char = sent.start_char
        sent_end_char = sent.end_char
        
        # Find start and end times by checking which words fall into this sentence range
        sent_start_time = None
        sent_end_time = None
        
        for w_start, w_end, t_start, t_end in words_info:
            # If word overlaps significantly with sentence
            if w_end > sent_start_char and w_start < sent_end_char:
                if sent_start_time is None or t_start < sent_start_time:
                    sent_start_time = t_start
                if sent_end_time is None or t_end > sent_end_time:
                    sent_end_time = t_end
                    
        results_list.append({
            'text': sent_text,
            'start': sent_start_time,
            'end': sent_end_time,
            'speaker_id': speaker if speaker != 'None' else None
        })

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_mark(nlp)
