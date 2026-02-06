import pandas as pd
import os
from rich import print as rprint
from core.spacy_utils.load_nlp_model import SPLIT_BY_MARK_FILE, SPLIT_BY_COMMA_FILE

def split_by_comma(text, nlp, max_length=60):
    if len(text) <= max_length:
        return [text]
    doc = nlp(text)
    parts = []
    last_idx = 0
    for token in doc:
        if token.text in [',', '，'] and token.idx > 10 and len(text) - token.idx > 10:
            parts.append(text[last_idx:token.idx+1].strip())
            last_idx = token.idx + 1
    parts.append(text[last_idx:].strip())
    return [p for p in parts if p]

def split_by_comma_main(nlp):
    df = pd.read_excel(SPLIT_BY_MARK_FILE)
    
    all_split_sentences = []
    for _, row in df.iterrows():
        sentence = str(row['text']).strip()
        speaker_id = row['speaker_id']
        start_time = row['start']
        end_time = row['end']
        
        split_sentences = split_by_comma(sentence, nlp)
        
        if len(split_sentences) <= 1:
            all_split_sentences.append({
                'text': sentence, 
                'start': start_time, 
                'end': end_time, 
                'speaker_id': speaker_id
            })
        else:
            total_len = sum(len(s) for s in split_sentences)
            current_start = start_time
            duration = end_time - start_time
            for s in split_sentences:
                s_duration = (len(s) / total_len) * duration if total_len > 0 else 0
                all_split_sentences.append({
                    'text': s,
                    'start': round(current_start, 3),
                    'end': round(current_start + s_duration, 3),
                    'speaker_id': speaker_id
                })
                current_start += s_duration

    df_output = pd.DataFrame(all_split_sentences)
    df_output.to_excel(SPLIT_BY_COMMA_FILE, index=False)
    
    # delete the original file
    if os.path.exists(SPLIT_BY_MARK_FILE):
        os.remove(SPLIT_BY_MARK_FILE)
    
    rprint(f"[green]💾 Sentences split by commas saved to →  `{SPLIT_BY_COMMA_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_comma_main(nlp)
    # nlp = init_nlp()
    # test = "So in the same frame, right there, almost in the exact same spot on the ice, Brown has committed himself, whereas McDavid has not."
    # print(split_by_comma(test, nlp))