import os
import pandas as pd
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_MARK_FILE
from core.utils.config_utils import load_key, get_joiner
from rich import print as rprint

warnings.filterwarnings("ignore", category=FutureWarning)

def split_by_mark(nlp):
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language # consider force english case
    joiner = get_joiner(language)
    rprint(f"[blue]🔍 Using {language} language joiner: '{joiner}'[/blue]")
    chunks = pd.read_excel("output/log/cleaned_chunks.xlsx")
    chunks.text = chunks.text.apply(lambda x: x.strip('"').strip(""))
    
    # join segments of the SAME speaker together, but force split when speaker changes
    sentences_by_mark = []
    
    # Group continuous chunks by speaker
    current_speaker = None
    current_speaker_text = ""
    
    for i, row in chunks.iterrows():
        text = str(row['text']).strip()
        speaker = row.get('speaker_id', None)
        
        if speaker != current_speaker:
            # When speaker changes, process the accumulated text for the previous speaker
            if current_speaker_text:
                doc = nlp(current_speaker_text)
                for sent in doc.sents:
                    s_text = sent.text.strip()
                    if s_text:
                        sentences_by_mark.append({'text': s_text, 'speaker_id': current_speaker})
            
            # Reset for new speaker
            current_speaker = speaker
            current_speaker_text = text
        else:
            # Same speaker, join with joiner
            if current_speaker_text:
                current_speaker_text += joiner + text
            else:
                current_speaker_text = text
                
    # Process the last speaker's text
    if current_speaker_text:
        doc = nlp(current_speaker_text)
        for sent in doc.sents:
            s_text = sent.text.strip()
            if s_text:
                sentences_by_mark.append({'text': s_text, 'speaker_id': current_speaker})

    # Punctuation merging logic
    final_sentences = []
    for i, item in enumerate(sentences_by_mark):
        text = item['text']
        speaker_id = item['speaker_id']
        if i > 0 and text.strip() in [',', '.', '，', '。', '？', '！'] and final_sentences:
            # ! If the current line contains only punctuation, merge it with the previous line
            final_sentences[-1]['text'] += text.strip()
        else:
            final_sentences.append({'text': text, 'speaker_id': speaker_id})

    # Save to Excel
    df_output = pd.DataFrame(final_sentences)
    df_output.to_excel(SPLIT_BY_MARK_FILE, index=False)
    
    rprint(f"[green]💾 Sentences split by punctuation marks saved to →  `{SPLIT_BY_MARK_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_mark(nlp)
