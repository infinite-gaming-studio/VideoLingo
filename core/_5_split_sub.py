import pandas as pd
from typing import List, Tuple
import concurrent.futures

from core._3_2_split_meaning import split_sentence
from core.prompts import get_align_prompt
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from core.utils import *
from core.utils.models import *
console = Console()

# ! You can modify your own weights here
# Chinese and Japanese 2.5 characters, Korean 2 characters, Thai 1.5 characters, full-width symbols 2 characters, other English-based and half-width symbols 1 character
def calc_len(text: str) -> float:
    text = str(text) # force convert
    def char_weight(char):
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF:  # Chinese and Japanese
            return 1.75
        elif 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF:  # Korean
            return 1.5
        elif 0x0E00 <= code <= 0x0E7F:  # Thai
            return 1
        elif 0xFF01 <= code <= 0xFF5E:  # full-width symbols
            return 1.75
        else:  # other characters (e.g. English and half-width symbols)
            return 1

    return sum(char_weight(char) for char in text)

def align_subs(src_sub: str, tr_sub: str, src_part: str) -> Tuple[List[str], List[str], str]:
    align_prompt = get_align_prompt(src_sub, tr_sub, src_part)
    
    src_parts = src_part.split('\n')
    expected_parts = len(src_parts)
    
    def valid_align(response_data):
        if 'align' not in response_data:
            return {"status": "error", "message": "Missing required key: `align`"}
        if len(response_data['align']) != expected_parts:
            return {"status": "error", "message": f"Align must contain exactly {expected_parts} parts, got {len(response_data['align'])}"}
        for i, item in enumerate(response_data['align']):
            key = f'target_part_{i+1}'
            if key not in item:
                return {"status": "error", "message": f"Missing required key: `{key}`"}
            # Check that the value is a string, not a dict or other type
            if not isinstance(item[key], str):
                return {"status": "error", "message": f"`{key}` must be a string, got {type(item[key]).__name__}: {item[key]}"}
        return {"status": "success", "message": "Align completed"}
    parsed = ask_gpt(align_prompt, resp_type='json', valid_def=valid_align, log_title='align_subs')
    align_data = parsed['align']
    tr_parts = [item[f'target_part_{i+1}'].strip() for i, item in enumerate(align_data)]
    
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)
    tr_remerged = joiner.join(tr_parts)
    
    table = Table(title="🔗 Aligned parts")
    table.add_column("Language", style="cyan")
    table.add_column("Parts", style="magenta")
    table.add_row("SRC_LANG", "\n".join(src_parts))
    table.add_row("TARGET_LANG", "\n".join(tr_parts))
    console.print(table)
    
    return src_parts, tr_parts, tr_remerged

def split_align_subs(src_lines: List[str], tr_lines: List[str], speaker_ids: List[str] = None):
    subtitle_set = load_key("subtitle")
    MAX_SUB_LENGTH = subtitle_set["max_length"]
    TARGET_SUB_MULTIPLIER = subtitle_set["target_multiplier"]
    # Handle NaN values: convert to empty string instead of 'nan'
    remerged_tr_lines = [str(tr) if pd.notna(tr) else '' for tr in tr_lines]
    
    to_split = []
    for i, (src, tr) in enumerate(zip(src_lines, tr_lines)):
        # Handle NaN values: convert to empty string instead of 'nan'
        src = str(src) if pd.notna(src) else ''
        tr = str(tr) if pd.notna(tr) else ''
        if len(src) > MAX_SUB_LENGTH or calc_len(tr) * TARGET_SUB_MULTIPLIER > MAX_SUB_LENGTH:
            to_split.append(i)
            table = Table(title=f"📏 Line {i} needs to be split")
            table.add_column("Type", style="cyan")
            table.add_column("Content", style="magenta")
            table.add_row("Source Line", src)
            table.add_row("Target Line", tr)
            console.print(table)
    
    @except_handler("Error in split_align_subs")
    def process(i):
        try:
            split_src = split_sentence(src_lines[i], num_parts=2).strip()
            src_parts, tr_parts, tr_remerged = align_subs(src_lines[i], tr_lines[i], split_src)
            src_lines[i] = src_parts
            tr_lines[i] = tr_parts
            remerged_tr_lines[i] = tr_remerged
        except Exception as e:
            console.print(f"[yellow]⚠️ Align failed for line {i}, using original: {e}[/yellow]")
            # Fallback: use original text without splitting
            src_val = str(src_lines[i]) if pd.notna(src_lines[i]) else ''
            tr_val = str(tr_lines[i]) if pd.notna(tr_lines[i]) else ''
            src_lines[i] = [src_val]
            tr_lines[i] = [tr_val]
            remerged_tr_lines[i] = tr_val
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=load_key("max_workers")) as executor:
        executor.map(process, to_split)
    
    # Flatten `src_lines` and `tr_lines`, tracking speaker_ids
    new_src_lines = []
    new_tr_lines = []
    new_speaker_ids = [] if speaker_ids is not None else None
    
    for i, sublist in enumerate(src_lines):
        items = sublist if isinstance(sublist, list) else [sublist]
        new_src_lines.extend(items)
        if speaker_ids is not None:
            new_speaker_ids.extend([speaker_ids[i]] * len(items))
    
    for sublist in tr_lines:
        items = sublist if isinstance(sublist, list) else [sublist]
        new_tr_lines.extend(items)
    
    return new_src_lines, new_tr_lines, remerged_tr_lines, new_speaker_ids

def split_for_sub_main():
    console.print("[bold green]🚀 Start splitting subtitles...[/bold green]")
    
    df = pd.read_excel(_4_2_TRANSLATION)
    src = df['Source'].tolist()
    trans = df['Translation'].tolist()
    speaker_ids = df['speaker_id'].tolist() if 'speaker_id' in df.columns else None
    
    subtitle_set = load_key("subtitle")
    MAX_SUB_LENGTH = subtitle_set["max_length"]
    TARGET_SUB_MULTIPLIER = subtitle_set["target_multiplier"]
    
    for attempt in range(3):  # 多次切割
        console.print(Panel(f"🔄 Split attempt {attempt + 1}", expand=False))
        split_src, split_trans, remerged, split_speaker_ids = split_align_subs(src.copy(), trans.copy(), speaker_ids.copy() if speaker_ids else None)
        
        # 检查是否所有字幕都符合长度要求
        if all(len(s) <= MAX_SUB_LENGTH for s in split_src) and \
           all(calc_len(tr) * TARGET_SUB_MULTIPLIER <= MAX_SUB_LENGTH for tr in split_trans):
            break
        
        # 更新源数据继续下一轮分割
        src, trans, speaker_ids = split_src, split_trans, split_speaker_ids

    # 循环结束后，src 和 trans 已经是最终的分割结果
    # 但由于 split_align_subs 内部可能对某些行进行了分割（变成列表），
    # 需要调用最后一次来确保所有数据都被展平
    split_src, split_trans, remerged, split_speaker_ids = split_align_subs(src.copy(), trans.copy(), speaker_ids.copy() if speaker_ids else None)
    
    # 确保二者有相同的长度，防止报错
    max_len = max(len(split_src), len(split_trans), len(remerged))
    if split_speaker_ids:
        max_len = max(max_len, len(split_speaker_ids))
    
    if len(split_src) < max_len:
        split_src += [""] * (max_len - len(split_src))
    if len(split_trans) < max_len:
        split_trans += [""] * (max_len - len(split_trans))
    if len(remerged) < max_len:
        remerged += [""] * (max_len - len(remerged))
    if split_speaker_ids and len(split_speaker_ids) < max_len:
        split_speaker_ids += [None] * (max_len - len(split_speaker_ids))
    
    # Save with speaker_id if available
    if split_speaker_ids:
        pd.DataFrame({'Source': split_src, 'Translation': split_trans, 'speaker_id': split_speaker_ids}).to_excel(_5_SPLIT_SUB, index=False)
        pd.DataFrame({'Source': split_src, 'Translation': remerged, 'speaker_id': split_speaker_ids}).to_excel(_5_REMERGED, index=False)
    else:
        pd.DataFrame({'Source': split_src, 'Translation': split_trans}).to_excel(_5_SPLIT_SUB, index=False)
        pd.DataFrame({'Source': split_src, 'Translation': remerged}).to_excel(_5_REMERGED, index=False)

if __name__ == '__main__':
    split_for_sub_main()
