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
        split_sentences = split_by_comma(sentence, nlp)
        for s in split_sentences:
            all_split_sentences.append({'text': s, 'speaker_id': speaker_id})

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