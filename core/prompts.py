import json
from core.utils import *

## ================================================================
# @ step4_splitbymeaning.py
def get_split_prompt(sentence, num_parts = 2, word_limit = 20):
    language = load_key("whisper.detected_language")
    split_prompt = f"""
## Role
You are a professional Netflix subtitle splitter in **{language}**.

## Task
Split the given subtitle text into **{num_parts}** parts, each less than **{word_limit}** words.

1. Maintain sentence meaning coherence according to Netflix subtitle standards
2. MOST IMPORTANT: Keep parts roughly equal in length (minimum 3 words each)
3. Split at natural points like punctuation marks or conjunctions
4. If provided text is repeated words, simply split at the middle of the repeated words.

## Steps
1. Analyze the sentence structure, complexity, and key splitting challenges
2. Generate two alternative splitting approaches with [br] tags at split positions
3. Compare both approaches highlighting their strengths and weaknesses
4. Choose the best splitting approach

## Given Text
<split_this_sentence>
{sentence}
</split_this_sentence>

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief description of sentence structure, complexity, and key splitting challenges",
    "split1": "First splitting approach with [br] tags at split positions",
    "split2": "Alternative splitting approach with [br] tags at split positions",
    "assess": "Comparison of both approaches highlighting their strengths and weaknesses",
    "choice": "1 or 2"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
""".strip()
    return split_prompt

def get_batch_split_prompt(sentences_list, word_limit=20):
    """
    sentences_list: list of dicts {"index": int, "sentence": str, "num_parts": int, "speaker_id": any}
    """
    language = load_key("whisper.detected_language")

    # Format the input sentences for the prompt
    input_text = ""
    for item in sentences_list:
        speaker_info = f"Speaker: {item['speaker_id']}\n" if item.get('speaker_id') is not None else ""
        input_text += f"ID: {item['index']}\n{speaker_info}Text: {item['sentence']}\nParts: {item['num_parts']}\n---\n"

    batch_split_prompt = f"""
## Role
You are a professional Netflix subtitle splitter in **{language}**.

## Task
Split several subtitle segments. For each segment, split it into the specified number of parts, each less than **{word_limit}** words.

1. Maintain sentence meaning coherence according to Netflix subtitle standards
2. MOST IMPORTANT: Keep parts roughly equal in length (minimum 3 words each)
3. Split at natural points like punctuation marks or conjunctions
4. If provided text is repeated words, simply split at the middle of the repeated words.
5. Note the speaker information if provided (for reference only, does not affect splitting)

## Input Segments
{input_text}

## Output Requirements
Output a JSON object where keys are the numeric IDs of the segments (same as the input ID field). For each ID, provide:
1. analysis: Brief description of splitting logic
2. split: The result text with [br] tags at split positions
3. speaker_assignments: Array of speaker IDs for each split part (same length as split parts). If the entire text belongs to the input speaker, repeat the speaker_id for each part.

## Output in only JSON format and no other text
```json
{{
    "1": {{
        "analysis": "...",
        "split": "part1 [br] part2",
        "speaker_assignments": ["SPEAKER_00", "SPEAKER_00"]
    }},
    "2": {{
        "analysis": "Text contains dialogue between two speakers",
        "split": "Speaker A says hello [br] Speaker B replies hi",
        "speaker_assignments": ["SPEAKER_00", "SPEAKER_01"]
    }}
}}
```

IMPORTANT: 
- Use the numeric ID directly as the key (e.g., "1", "2"), NOT "ID_1" or "ID_2" format.
- speaker_assignments array length must match the number of split parts.
- If text contains multiple speakers' dialogue, analyze and assign correct speaker to each part.
Note: Start your answer with ```json and end with ```, do not add any other text.
""".strip()
    return batch_split_prompt

"""{{
    "analysis": "Brief analysis of the text structure",
    "split": "Complete sentence with [br] tags at split positions"
}}"""

## ================================================================
# @ step4_1_summarize.py
def get_summary_prompt(source_content, custom_terms_json=None):
    src_lang = load_key("whisper.detected_language")
    tgt_lang = load_key("target_language")
    
    # add custom terms note
    terms_note = ""
    if custom_terms_json:
        terms_list = []
        for term in custom_terms_json['terms']:
            terms_list.append(f"- {term['src']}: {term['tgt']} ({term['note']})")
        terms_note = "\n### Existing Terms\nPlease exclude these terms in your extraction:\n" + "\n".join(terms_list)
    
    summary_prompt = f"""
## Role
You are a video translation expert and terminology consultant, specializing in {src_lang} comprehension and {tgt_lang} expression optimization.

## Task
For the provided {src_lang} video text:
1. Summarize main topic in two sentences
2. Extract professional terms/names with {tgt_lang} translations (excluding existing terms)
3. Provide brief explanation for each term

{terms_note}

Steps:
1. Topic Summary:
   - Quick scan for general understanding
   - Write two sentences: first for main topic, second for key point
2. Term Extraction:
   - Mark professional terms and names (excluding those listed in Existing Terms)
   - Provide {tgt_lang} translation or keep original
   - Add brief explanation
   - Extract less than 15 terms

## INPUT
<text>
{source_content}
</text>

## Output in only JSON format and no other text
{{
  "theme": "Two-sentence video summary",
  "terms": [
    {{
      "src": "{src_lang} term",
      "tgt": "{tgt_lang} translation or original", 
      "note": "Brief explanation"
    }},
    ...
  ]
}}  

## Example
{{
  "theme": "本视频介绍人工智能在医疗领域的应用现状。重点展示了AI在医学影像诊断和药物研发中的突破性进展。",
  "terms": [
    {{
      "src": "Machine Learning",
      "tgt": "机器学习",
      "note": "AI的核心技术，通过数据训练实现智能决策"
    }},
    {{
      "src": "CNN",
      "tgt": "CNN",
      "note": "卷积神经网络，用于医学图像识别的深度学习模型"
    }}
  ]
}}

Note: Start you answer with ```json and end with ```, do not add any other text.
""".strip()
    return summary_prompt

## ================================================================
# @ step5_translate.py & translate_lines.py
def generate_shared_prompt(previous_content_prompt, after_content_prompt, summary_prompt, things_to_note_prompt):
    return f'''### Context Information
<previous_content>
{previous_content_prompt}
</previous_content>

<subsequent_content>
{after_content_prompt}
</subsequent_content>

### Content Summary
{summary_prompt}

### Points to Note
{things_to_note_prompt}'''

def get_prompt_faithfulness(lines_with_ids, shared_prompt):
    """
    Generate prompt for faithful translation.
    
    Args:
        lines_with_ids: List of dicts with 'id', 'text', 'speaker_id', 'labeled_text'
    """
    TARGET_LANGUAGE = load_key("target_language")
    
    # Build input text and JSON format using independent IDs
    input_lines = []
    json_dict = {}
    
    for item in lines_with_ids:
        line_id = str(item['id'])
        labeled_text = item['labeled_text']
        input_lines.append(labeled_text)
        json_dict[line_id] = {
            "id": item['id'],  # 保留原始 ID 用于关联
            "origin": labeled_text, 
            "direct": f"direct {TARGET_LANGUAGE} translation for line {item['id']}."
        }
    
    input_text = "\n".join(input_lines)
    json_format = json.dumps(json_dict, indent=2, ensure_ascii=False)

    src_language = load_key("whisper.detected_language")
    prompt_faithfulness = f'''
## Role
You are a professional Netflix subtitle translator, fluent in both {src_language} and {TARGET_LANGUAGE}, as well as their respective cultures. 
Your expertise lies in accurately understanding the semantics and structure of the original {src_language} text and faithfully translating it into {TARGET_LANGUAGE} while preserving the original meaning.

## Task
We have a segment of original {src_language} subtitles that need to be directly translated into {TARGET_LANGUAGE}. These subtitles come from a specific context and may contain specific themes and terminology.
The lines may be prefixed with `[SPEAKER_N]:` to indicate different speakers. Use this information to better understand the dialogue context (e.g., gender, tone, relationships), but **DO NOT** include the speaker prefix in your translation result.

1. Translate the original {src_language} subtitles into {TARGET_LANGUAGE} line by line
2. Ensure the translation is faithful to the original, accurately conveying the original meaning
3. Consider the context (including speaker info) and professional terminology
4. **IMPORTANT**: Preserve the exact "id" field in your output for each line

{shared_prompt}

<translation_principles>
1. Faithful to the original: Accurately convey the content and meaning of the original text, without arbitrarily changing, adding, or omitting content.
2. Accurate terminology: Use professional terms correctly and maintain consistency in terminology.
3. Understand the context: Fully comprehend and reflect the background and contextual relationships of the text (e.g. who is speaking).
4. ID preservation: You must preserve the "id" field in each line's output to ensure correct association.
</translation_principles>

## INPUT
<subtitles>
{input_text}
</subtitles>

## Output in only JSON format and no other text
```json
{json_format}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''
    return prompt_faithfulness.strip()


def get_prompt_expressiveness(faithfulness_result, lines_with_ids, shared_prompt):
    """
    Generate prompt for expressive translation.
    
    Args:
        faithfulness_result: Dict with line_id as key, containing 'id', 'origin', 'direct'
        lines_with_ids: Original list of dicts with 'id', 'text', 'speaker_id'
    """
    TARGET_LANGUAGE = load_key("target_language")
    
    # Build input text from lines_with_ids
    input_lines = []
    for item in lines_with_ids:
        input_lines.append(item['labeled_text'])
    input_text = "\n".join(input_lines)
    
    # Build JSON format preserving IDs
    json_format = {}
    for key, value in faithfulness_result.items():
        json_format[key] = {
            "id": value.get("id", key),  # 保留原始 ID
            "origin": value["origin"],
            "direct": value["direct"],
            "reflect": "your reflection on direct translation",
            "free": "your free translation"
        }
    json_format = json.dumps(json_format, indent=2, ensure_ascii=False)

    src_language = load_key("whisper.detected_language")
    prompt_expressiveness = f'''
## Role
You are a professional Netflix subtitle translator and language consultant.
Your expertise lies not only in accurately understanding the original {src_language} but also in optimizing the {TARGET_LANGUAGE} translation to better suit the target language's expression habits and cultural background.

## Task
We already have a direct translation version of the original {src_language} subtitles.
Your task is to reflect on and improve these direct translations to create more natural and fluent {TARGET_LANGUAGE} subtitles.
The original lines may be prefixed with `[SPEAKER_N]:` to indicate different speakers. Use this information to better understand the dialogue context, but **DO NOT** include the speaker prefix in your free translation result.

1. Analyze the direct translation results line by line, pointing out existing issues
2. Provide detailed modification suggestions
3. Perform free translation based on your analysis
4. Do not add comments or explanations in the translation, as the subtitles are for the audience to read
5. Do not leave empty lines in the free translation, as the subtitles are for the audience to read
6. **IMPORTANT**: Preserve the exact "id" field in your output for each line

{shared_prompt}

<Translation Analysis Steps>
Please use a two-step thinking process to handle the text line by line:

1. Direct Translation Reflection:
   - Evaluate language fluency
   - Check if the language style is consistent with the original text and context (speaker)
   - Check the conciseness of the subtitles, point out where the translation is too wordy

2. {TARGET_LANGUAGE} Free Translation:
   - Aim for contextual smoothness and naturalness, conforming to {TARGET_LANGUAGE} expression habits
   - Ensure it's easy for {TARGET_LANGUAGE} audience to understand and accept
   - Adapt the language style to match the theme and speaker (e.g. different tones for different characters)
</Translation Analysis Steps>
   
## INPUT
<subtitles>
{input_text}
</subtitles>

## Output in only JSON format and no other text
```json
{json_format}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''
    return prompt_expressiveness.strip()


## ================================================================
# @ step6_splitforsub.py
def get_align_prompt(src_sub, tr_sub, src_part):
    targ_lang = load_key("target_language")
    src_lang = load_key("whisper.detected_language")
    src_splits = src_part.split('\n')
    num_parts = len(src_splits)
    src_part = src_part.replace('\n', ' [br] ')
    align_parts_json = ','.join(
        f'''
        {{
            "src_part_{i+1}": "{src_splits[i]}",
            "target_part_{i+1}": "Corresponding aligned {targ_lang} subtitle part"
        }}''' for i in range(num_parts)
    )

    align_prompt = f'''
## Role
You are a Netflix subtitle alignment expert fluent in both {src_lang} and {targ_lang}.

## Task
We have {src_lang} and {targ_lang} original subtitles for a Netflix program, as well as a pre-processed split version of {src_lang} subtitles.
Your task is to create the best splitting scheme for the {targ_lang} subtitles based on this information.

1. Analyze the word order and structural correspondence between {src_lang} and {targ_lang} subtitles
2. Split the {targ_lang} subtitles according to the pre-processed {src_lang} split version
3. Never leave empty lines. If it's difficult to split based on meaning, you may appropriately rewrite the sentences that need to be aligned
4. Do not add comments or explanations in the translation, as the subtitles are for the audience to read

## INPUT
<subtitles>
{src_lang} Original: "{src_sub}"
{targ_lang} Original: "{tr_sub}"
Pre-processed {src_lang} Subtitles ([br] indicates split points): {src_part}
</subtitles>

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief analysis of word order, structure, and semantic correspondence between two subtitles",
    "align": [
        {align_parts_json}
    ]
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()
    return align_prompt

## ================================================================
# @ step8_gen_audio_task.py @ step10_gen_audio.py
def get_subtitle_trim_prompt(text, duration):
 
    rule = '''Consider a. Reducing filler words without modifying meaningful content. b. Omitting unnecessary modifiers or pronouns, for example:
    - "Please explain your thought process" can be shortened to "Please explain thought process"
    - "We need to carefully analyze this complex problem" can be shortened to "We need to analyze this problem"
    - "Let's discuss the various different perspectives on this topic" can be shortened to "Let's discuss different perspectives on this topic"
    - "Can you describe in detail your experience from yesterday" can be shortened to "Can you describe yesterday's experience" '''

    trim_prompt = f'''
## Role
You are a professional subtitle editor, editing and optimizing lengthy subtitles that exceed voiceover time before handing them to voice actors. 
Your expertise lies in cleverly shortening subtitles slightly while ensuring the original meaning and structure remain unchanged.
 
## INPUT
<subtitles>
Subtitle: "{text}"
Duration: {duration} seconds
</subtitles>

## Processing Rules
{rule}

## Processing Steps
Please follow these steps and provide the results in the JSON output:
1. Analysis: Briefly analyze the subtitle's structure, key information, and filler words that can be omitted.
2. Trimming: Based on the rules and analysis, optimize the subtitle by making it more concise according to the processing rules.

## Output in only JSON format and no other text
```json
{{
    "analysis": "Brief analysis of the subtitle, including structure, key information, and potential processing locations",
    "result": "Optimized and shortened subtitle in the original subtitle language"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()
    return trim_prompt

def get_batch_subtitle_trim_prompt(batches, duration_limit):
    """
    batches: list of dicts {"id": int, "text": str, "duration": float}
    """
    rule = '''Consider a. Reducing filler words without modifying meaningful content. b. Omitting unnecessary modifiers or pronouns, for example:
    - "Please explain your thought process" can be shortened to "Please explain thought process"
    - "We need to carefully analyze this complex problem" can be shortened to "We need to analyze this problem"
    - "Let's discuss the various different perspectives on this topic" can be shortened to "Let's discuss different perspectives on this topic"
    - "Can you describe in detail your experience from yesterday" can be shortened to "Can you describe yesterday's experience" '''

    input_text = ""
    for item in batches:
        input_text += f"ID: {item['id']}\nText: \"{item['text']}\"\nDuration Limit: {item['duration']} seconds\n---\n"

    trim_prompt = f"""
## Role
You are a professional subtitle editor. Your task is to shorten multiple subtitles to fit their respective time durations while preserving meaning.

## Input Subtitles
{input_text}

## Processing Rules
{rule}

## Output Requirements
Output a JSON object where keys are the numeric IDs of the subtitles. Each value should be the optimized and shortened subtitle text.

## Output in only JSON format and no other text
```json
{{
    "1": "shortened text 1",
    "2": "shortened text 2",
    ...
}}
```

IMPORTANT: Use the numeric ID directly as the key (e.g., "1", "2"), NOT "ID_1" or "ID_2" format.
Note: Start your answer with ```json and end with ```, do not add any other text.
""".strip()
    return trim_prompt

## ================================================================
# @ tts_main
def get_correct_text_prompt(text):
    return f'''
## Role
You are a text cleaning expert for TTS (Text-to-Speech) systems.

## Task
Clean the given text by:
1. Keep only basic punctuation (.,?!)
2. Preserve the original meaning

## INPUT
{text}

## Output in only JSON format and no other text
```json
{{
    "text": "cleaned text here"
}}
```

Note: Start you answer with ```json and end with ```, do not add any other text.
'''.strip()

def get_speaker_profile_prompt(speaker_id, text, tts_method):
    return f"""
## Role
You are a voice assignment expert for video dubbing. Your task is to analyze a speaker's dialogue and recommend the most suitable TTS voice.

## Task
Based on the provided dialogue, determine the speaker's likely:
1. Gender (Male/Female)
2. Tone (e.g., Professional, Excited, Calm, Authoritative)
3. Age Group (e.g., Young, Adult, Senior)

Then, recommend a specific voice for the TTS method: **{tts_method}**.

## Dialogue Sample from {speaker_id}
{text}

## Output in only JSON format
```json
{{
    "gender": "Male/Female",
    "tone": "Brief description",
    "age": "Brief description",
    "recommended_voice": "Specific voice name (e.g., for edge_tts use 'en-US-JennyNeural' style)"
}}
```
""".strip()
