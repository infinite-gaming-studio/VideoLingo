import pandas as pd
import os
from rich import print as rprint
from core.spacy_utils.load_nlp_model import SPLIT_BY_COMMA_FILE, SPLIT_BY_CONNECTOR_FILE

CONNECTORS = [' but ', ' and ', ' or ', ' so ', ' yet ', ' for ', ' nor ', ' however ', ' therefore ', ' nevertheless ', ' moreover ', ' furthermore ', ' consequently ', ' besides ', ' meanwhile ']

def split_by_connectors(text, nlp, max_length=60):
    if len(text) <= max_length:
        return [text]
    for connector in CONNECTORS:
        if connector in text:
            parts = text.split(connector, 1)
            return [parts[0].strip(), connector.strip() + ' ' + parts[1].strip()]
    return [text]

def split_sentences_main(nlp):
    # Read input sentences
    df = pd.read_excel(SPLIT_BY_COMMA_FILE)
    
    all_split_sentences = []
    # Process each input sentence
    for _, row in df.iterrows():
        sentence = str(row['text']).strip()
        speaker_id = row['speaker_id']
        split_sentences = split_by_connectors(sentence, nlp = nlp)
        for s in split_sentences:
            all_split_sentences.append({'text': s, 'speaker_id': speaker_id})
    
    df_output = pd.DataFrame(all_split_sentences)
    df_output.to_excel(SPLIT_BY_CONNECTOR_FILE, index=False)

    # delete the original file
    if os.path.exists(SPLIT_BY_COMMA_FILE):
        os.remove(SPLIT_BY_COMMA_FILE)
    
    rprint(f"[green]💾 Sentences split by connectors saved to →  `{SPLIT_BY_CONNECTOR_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_sentences_main(nlp)
    # nlp = init_nlp()
    # a = "and show the specific differences that make a difference between a breakaway that results in a goal in the NHL versus one that doesn't."
    # print(split_by_connectors(a, nlp))