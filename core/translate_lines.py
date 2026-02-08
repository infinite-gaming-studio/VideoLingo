from core.prompts import generate_shared_prompt, get_prompt_faithfulness, get_prompt_expressiveness
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box
from core.utils import *
console = Console()

def valid_translate_result(result: dict, expected_ids: set, required_sub_keys: list):
    """
    Validate translation result with independent IDs.
    
    Args:
        result: Dict with line_id as key
        expected_ids: Set of expected line IDs
        required_sub_keys: List of required sub-keys
    """
    result_ids = set(result.keys())
    
    # Check if all expected IDs are present
    if result_ids != expected_ids:
        missing = expected_ids - result_ids
        extra = result_ids - expected_ids
        msg = []
        if missing:
            msg.append(f"Missing IDs: {missing}")
        if extra:
            msg.append(f"Extra IDs: {extra}")
        return {"status": "error", "message": "; ".join(msg)}
    
    # Check for required sub-keys in all items
    for key, item in result.items():
        # Check if 'id' field matches the key
        if 'id' not in item:
            return {"status": "error", "message": f"Missing 'id' field in item {key}"}
        if str(item['id']) != str(key):
            return {"status": "error", "message": f"ID mismatch in item {key}: expected {key}, got {item['id']}"}
        
        # Check other required fields
        for sub_key in required_sub_keys:
            if sub_key not in item:
                return {"status": "error", "message": f"Missing '{sub_key}' in item {key}"}

    return {"status": "success", "message": "Translation completed"}

def translate_lines(lines_with_ids, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt, index = 0):
    """
    Translate lines with independent ID association.
    
    Args:
        lines_with_ids: List of dicts with 'id', 'text', 'speaker_id', 'labeled_text'
    
    Returns:
        List of dicts with 'id', 'translation', 'speaker_id'
    """
    shared_prompt = generate_shared_prompt(previous_content_prompt, after_cotent_prompt, summary_prompt, things_to_note_prompt)
    
    # Get expected IDs for validation
    expected_ids = {str(item['id']) for item in lines_with_ids}
    line_count = len(lines_with_ids)

    # Retry translation if validation fails
    def retry_translation(prompt, step_name):
        def valid_faith(response_data):
            return valid_translate_result(response_data, expected_ids, ['direct'])
        def valid_express(response_data):
            return valid_translate_result(response_data, expected_ids, ['free'])
        for retry in range(3):
            if step_name == 'faithfulness':
                result = ask_gpt(prompt+retry* " ", resp_type='json', valid_def=valid_faith, log_title=f'translate_{step_name}')
            elif step_name == 'expressiveness':
                result = ask_gpt(prompt+retry* " ", resp_type='json', valid_def=valid_express, log_title=f'translate_{step_name}')
            if len(result) == line_count:
                return result
            if retry != 2:
                console.print(f'[yellow]⚠️ {step_name.capitalize()} translation of block {index} failed (ID mismatch or length error), Retry...[/yellow]')
        raise ValueError(f'[red]❌ {step_name.capitalize()} translation of block {index} failed after 3 retries. Please check `output/gpt_log/error.json` for more details.[/red]')

    ## Step 1: Faithful to the Original Text
    prompt1 = get_prompt_faithfulness(lines_with_ids, shared_prompt)
    faith_result = retry_translation(prompt1, 'faithfulness')

    for i in faith_result:
        faith_result[i]["direct"] = faith_result[i]["direct"].replace('\n', ' ')

    # If reflect_translate is False or not set, use faithful translation directly
    reflect_translate = load_key('reflect_translate')
    if not reflect_translate:
        # Build result with IDs
        result_list = []
        for key in sorted(faith_result.keys(), key=lambda x: int(x) if x.isdigit() else x):
            item = faith_result[key]
            # Find matching original data by ID
            orig_data = next((d for d in lines_with_ids if str(d['id']) == str(key)), None)
            if orig_data:
                result_list.append({
                    'id': orig_data['id'],
                    'text': orig_data['text'],
                    'translation': item['direct'].strip(),
                    'speaker_id': orig_data['speaker_id'],
                    'start': orig_data.get('start'),
                    'end': orig_data.get('end')
                })
        
        table = Table(title="Translation Results", show_header=False, box=box.ROUNDED)
        table.add_column("Translations", style="bold")
        for i, key in enumerate(faith_result):
            table.add_row(f"[cyan]Origin:  {faith_result[key]['origin']}[/cyan]")
            table.add_row(f"[magenta]Direct:  {faith_result[key]['direct']}[/magenta]")
            if i < len(faith_result) - 1:
                table.add_row("[yellow]" + "-" * 50 + "[/yellow]")
        
        console.print(table)
        return result_list

    ## Step 2: Express Smoothly  
    prompt2 = get_prompt_expressiveness(faith_result, lines_with_ids, shared_prompt)
    express_result = retry_translation(prompt2, 'expressiveness')

    table = Table(title="Translation Results", show_header=False, box=box.ROUNDED)
    table.add_column("Translations", style="bold")
    for i, key in enumerate(express_result):
        table.add_row(f"[cyan]Origin:  {faith_result[key]['origin']}[/cyan]")
        table.add_row(f"[magenta]Direct:  {faith_result[key]['direct']}[/magenta]")
        table.add_row(f"[green]Free:    {express_result[key]['free']}[/green]")
        if i < len(express_result) - 1:
            table.add_row("[yellow]" + "-" * 50 + "[/yellow]")

    console.print(table)

    # Build result with IDs
    result_list = []
    for key in sorted(express_result.keys(), key=lambda x: int(x) if x.isdigit() else x):
        item = express_result[key]
        # Find matching original data by ID
        orig_data = next((d for d in lines_with_ids if str(d['id']) == str(key)), None)
        if orig_data:
            result_list.append({
                'id': orig_data['id'],
                'text': orig_data['text'],
                'translation': item['free'].replace('\n', ' ').strip(),
                'speaker_id': orig_data['speaker_id'],
                'start': orig_data.get('start'),
                'end': orig_data.get('end')
            })

    if len(result_list) != line_count:
        console.print(Panel(f'[red]❌ Translation of block {index} failed, Length Mismatch, Please check `output/gpt_log/translate_expressiveness.json`[/red]'))
        raise ValueError(f'Expected {line_count} lines, but got {len(result_list)}')

    return result_list


if __name__ == '__main__':
    # test e.g.
    lines = '''All of you know Andrew Ng as a famous computer science professor at Stanford.
He was really early on in the development of neural networks with GPUs.
Of course, a creator of Coursera and popular courses like deeplearning.ai.
Also the founder and creator and early lead of Google Brain.'''
    previous_content_prompt = None
    after_cotent_prompt = None
    things_to_note_prompt = None
    summary_prompt = None
    translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt)