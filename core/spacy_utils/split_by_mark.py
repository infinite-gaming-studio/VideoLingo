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
    
    # Calculate character offsets for speaker mapping
    offsets = []
    current_offset = 0
    for text in chunks.text:
        offsets.append(current_offset)
        current_offset += len(text) + len(joiner)

    # join with joiner
    input_text = joiner.join(chunks.text.to_list())

    doc = nlp(input_text)
    assert doc.has_annotation("SENT_START")

    # skip - and ...
    sentences_by_mark = []
    current_sentence_parts = []
    
    # iterate all sentences
    for sent in doc.sents:
        text = sent.text.strip()
        
        # Find speaker_id for this sentence part based on its start position in input_text
        sent_start_offset = sent.start_char
        chunk_idx = 0
        while chunk_idx < len(offsets) - 1 and offsets[chunk_idx+1] <= sent_start_offset:
            chunk_idx += 1
        speaker_id = chunks.iloc[chunk_idx].get('speaker_id', None)

        # check if the current sentence ends with - or ...
        if current_sentence_parts and (
            text.startswith('-') or 
            text.startswith('...') or
            current_sentence_parts[-1]['text'].endswith('-') or
            current_sentence_parts[-1]['text'].endswith('...')
        ):
            current_sentence_parts.append({'text': text, 'speaker_id': speaker_id})
        else:
            if current_sentence_parts:
                combined_text = ' '.join([p['text'] for p in current_sentence_parts])
                # Use speaker_id of the first part as representative
                sentences_by_mark.append({'text': combined_text, 'speaker_id': current_sentence_parts[0]['speaker_id']})
                current_sentence_parts = []
            current_sentence_parts.append({'text': text, 'speaker_id': speaker_id})
    
    # add the last sentence
    if current_sentence_parts:
        combined_text = ' '.join([p['text'] for p in current_sentence_parts])
        sentences_by_mark.append({'text': combined_text, 'speaker_id': current_sentence_parts[0]['speaker_id']})

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
