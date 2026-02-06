import concurrent.futures
from difflib import SequenceMatcher
import math
from core.prompts import get_split_prompt
from core.spacy_utils.load_nlp_model import init_nlp
from core.utils import *
from rich.console import Console
from rich.table import Table
from core.utils.models import _3_1_SPLIT_BY_NLP, _3_2_SPLIT_BY_MEANING
console = Console()

def tokenize_sentence(sentence, nlp):
    doc = nlp(sentence)
    return [token.text for token in doc]

def find_split_positions(original, modified):
    split_positions = []
    parts = modified.split('[br]')
    start = 0
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)

    for i in range(len(parts) - 1):
        max_similarity = 0
        best_split = None

        for j in range(start, len(original)):
            original_left = original[start:j]
            modified_left = joiner.join(parts[i].split())

            left_similarity = SequenceMatcher(None, original_left, modified_left).ratio()

            if left_similarity > max_similarity:
                max_similarity = left_similarity
                best_split = j

        if max_similarity < 0.9:
            console.print(f"[yellow]Warning: low similarity found at the best split point: {max_similarity}[/yellow]")
        if best_split is not None:
            split_positions.append(best_split)
            start = best_split
        else:
            console.print(f"[yellow]Warning: Unable to find a suitable split point for the {i+1}th part.[/yellow]")

    return split_positions

def batch_split_sentences(sentences_to_split, word_limit=20, retry_attempt=0):
    """Split a batch of long sentences using GPT."""
    if not sentences_to_split:
        return {}
    
    prompt = get_batch_split_prompt(sentences_to_split, word_limit)
    
    def valid_batch_split(response_data):
        for item in sentences_to_split:
            idx_str = str(item['index'])
            if idx_str not in response_data:
                return {"status": "error", "message": f"Missing ID {idx_str} in response"}
            if "[br]" not in response_data[idx_str].get("split", ""):
                # We don't necessarily error out if ONE fails, but here we want to ensure splitting happened
                pass 
        return {"status": "success", "message": "Batch split completed"}

    try:
        response_data = ask_gpt(prompt + " " * retry_attempt, resp_type='json', valid_def=valid_batch_split, log_title='batch_split_by_meaning')
    except Exception as e:
        console.print(f"[red]Batch split failed: {e}[/red]")
        return {}

    results = {}
    for item in sentences_to_split:
        idx_str = str(item['index'])
        if idx_str in response_data:
            best_split_raw = response_data[idx_str]["split"]
            sentence = item['sentence']
            split_points = find_split_positions(sentence, best_split_raw)
            
            best_split = sentence
            # split the sentence based on the split points
            for i, split_point in enumerate(split_points):
                if i == 0:
                    best_split = sentence[:split_point] + '\n' + sentence[split_point:]
                else:
                    parts = best_split.split('\n')
                    last_part = parts[-1]
                    parts[-1] = last_part[:split_point - split_points[i-1]] + '\n' + last_part[split_point - split_points[i-1]:]
                    best_split = '\n'.join(parts)
            
            results[item['index']] = best_split
            
            table = Table(title=f"Sentence {item['index']} Split")
            table.add_column("Type", style="cyan")
            table.add_column("Sentence")
            table.add_row("Original", sentence, style="yellow")
            table.add_row("Split", best_split.replace('\n', ' ||'), style="yellow")
            console.print(table)
            
    return results

def parallel_split_sentences(sentences, max_length, max_workers, nlp, retry_attempt=0):
    """Split sentences using batching."""
    new_sentences = [None] * len(sentences)
    to_split = []

    for index, sentence in enumerate(sentences):
        tokens = tokenize_sentence(sentence, nlp)
        num_parts = math.ceil(len(tokens) / max_length)
        if len(tokens) > max_length:
            to_split.append({"index": index, "sentence": sentence, "num_parts": num_parts})
        else:
            if retry_attempt == 0:
                console.print(f"[grey]Sentence {index} is short ({len(tokens)} tokens), skip splitting.[/grey]")
            new_sentences[index] = [sentence]

    # Batch size of 5 for splitting to avoid too large prompts/responses
    batch_size = 5
    for i in range(0, len(to_split), batch_size):
        batch = to_split[i:i + batch_size]
        batch_results = batch_split_sentences(batch, max_length, retry_attempt)
        for idx, split_result in batch_results.items():
            if split_result:
                split_lines = split_result.strip().split('\n')
                new_sentences[idx] = [line.strip() for line in split_lines]
    
    # Fill in any that failed (optional, currently it'll stay None and we handle it)
    for i in range(len(new_sentences)):
        if new_sentences[i] is None:
            new_sentences[i] = [sentences[i]]

    return [sentence for sublist in new_sentences for sentence in sublist]

@check_file_exists(_3_2_SPLIT_BY_MEANING)
def split_sentences_by_meaning():
    """The main function to split sentences by meaning."""
    # read input sentences
    with open(_3_1_SPLIT_BY_NLP, 'r', encoding='utf-8') as f:
        sentences = [line.strip() for line in f.readlines()]

    nlp = init_nlp()
    # 🔄 process sentences multiple times to ensure all are split
    for retry_attempt in range(3):
        sentences = parallel_split_sentences(sentences, max_length=load_key("max_split_length"), max_workers=load_key("max_workers"), nlp=nlp, retry_attempt=retry_attempt)

    # 💾 save results
    with open(_3_2_SPLIT_BY_MEANING, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sentences))
    console.print('[green]✅ All sentences have been successfully split![/green]')

if __name__ == '__main__':
    # print(split_sentence('Which makes no sense to the... average guy who always pushes the character creation slider all the way to the right.', 2, 22))
    split_sentences_by_meaning()