import pandas as pd
import os
import string
from rich import print as rprint
from core.spacy_utils.load_nlp_model import SPLIT_BY_CONNECTOR_FILE
from core.utils.models import _3_1_SPLIT_BY_NLP

def split_long_sentence(doc):
    """Split a long sentence by its root or other logical points."""
    root = [token for token in doc if token.head == token][0]
    split_idx = root.i
    if split_idx > 0 and split_idx < len(doc) - 1:
        return [doc[:split_idx].text.strip(), doc[split_idx:].text.strip()]
    return [doc.text]

def split_extremely_long_sentence(doc, max_tokens=30):
    """Fallback for extremely long sentences using simple indexing."""
    text = doc.text
    tokens = [t.text for t in doc]
    if len(tokens) <= max_tokens:
        return [text]
    return [" ".join(tokens[:max_tokens]), " ".join(tokens[max_tokens:])]

def split_long_by_root_main(nlp):
    df = pd.read_excel(SPLIT_BY_CONNECTOR_FILE)
    
    all_split_sentences = []
    for _, row in df.iterrows():
        sentence = str(row['text']).strip()
        speaker_id = row['speaker_id']
        doc = nlp(sentence)
        if len(doc) > 40:
            split_sentences = split_long_sentence(doc)
            if any(len(nlp(sent)) > 40 for sent in split_sentences):
                split_sentences = [subsent for sent in split_sentences for subsent in split_extremely_long_sentence(nlp(sent))]
            for s in split_sentences:
                all_split_sentences.append({'text': s, 'speaker_id': speaker_id})
            rprint(f"[yellow]✂️  Splitting long sentences by root: {sentence[:30]}...[/yellow]")
        else:
            all_split_sentences.append({'text': sentence, 'speaker_id': speaker_id})

    punctuation = string.punctuation + "'" + '"'  # include all punctuation and apostrophe ' and "

    final_results = []
    for i, item in enumerate(all_split_sentences):
        sentence = item['text']
        speaker_id = item['speaker_id']
        stripped_sentence = sentence.strip()
        if not stripped_sentence or all(char in punctuation for char in stripped_sentence):
            rprint(f"[yellow]⚠️  Warning: Empty or punctuation-only line detected at index {i}[/yellow]")
            if i > 0:
                final_results[-1]['text'] += sentence
            continue
        final_results.append({'text': sentence, 'speaker_id': speaker_id})

    df_output = pd.DataFrame(final_results)
    df_output.to_excel(_3_1_SPLIT_BY_NLP, index=False)

    # delete the original file
    if os.path.exists(SPLIT_BY_CONNECTOR_FILE):
        os.remove(SPLIT_BY_CONNECTOR_FILE)   

    rprint(f"[green]💾 Long sentences split by root saved to →  {_3_1_SPLIT_BY_NLP}[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_long_by_root_main(nlp)
    # raw = "平口さんの盛り上げごまが初めて売れました本当に嬉しいです本当にやっぱり見た瞬間いいって言ってくれるそういうコマを作るのがやっぱりいいですよねその2ヶ月後チコさんが何やらそわそわしていましたなんか気持ち悪いやってきたのは平口さんの駒の評判を聞きつけた愛知県の収集家ですこの男性師匠大沢さんの駒も持っているといいますちょっと褒めすぎかなでも確実にファンは広がっているようです自信がない部分をすごく感じてたのでこれで自信を持って進んでくれるなっていう本当に始まったばっかりこれからいろいろ挑戦していってくれるといいなと思って今月平口さんはある場所を訪れましたこれまで数々のタイトル戦でコマを提供してきた老舗5番手平口さんのコマを扱いたいと言いますいいですねぇ困ってだんだん成長しますので大切に使ってそういう長く良い駒になる駒ですね商談が終わった後店主があるものを取り出しましたこの前の名人戦で使った駒があるんですけど去年、名人銭で使われた盛り上げごま低く盛り上げて品良くするというのは難しい素晴らしいですね平口さんが目指す高みですこういった感じで作れればまだまだですけどただ、多分、咲く。"
    # nlp = init_nlp()
    # doc = nlp(raw.strip())
    # for sent in split_still_long_sentence(doc):
    #     print(sent, '\n==========')
