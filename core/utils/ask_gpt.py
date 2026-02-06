import os
import json
from threading import Lock
import json_repair
from openai import OpenAI
from core.utils.config_utils import load_key, update_key
from core.utils.logger import vprint, log_api_call
from core.utils.decorator import except_handler
import time

# ------------
# cache gpt response
# ------------

LOCK = Lock()
GPT_LOG_FOLDER = 'output/gpt_log'

# ------------
# rate limit controller
# ------------

class RateLimiter:
    def __init__(self):
        self.lock = Lock()
        self.last_429_time = 0
        self.cooldown_duration = 0
        self.consecutive_success = 0

    def wait_if_needed(self):
        with self.lock:
            if self.cooldown_duration > 0:
                elapsed = time.time() - self.last_429_time
                wait_time = max(0, self.cooldown_duration - elapsed)
                if wait_time > 0:
                    vprint(f"Rate limit cooldown: waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)

    def report_error(self, is_429):
        with self.lock:
            if is_429:
                self.last_429_time = time.time()
                # Exponential growth: 2s -> 4s -> 8s ... max 60s
                if self.cooldown_duration == 0:
                    self.cooldown_duration = 2
                else:
                    self.cooldown_duration = min(self.cooldown_duration * 2, 60)
                self.consecutive_success = 0
                vprint(f"Rate limit detected! Setting cooldown to {self.cooldown_duration}s")

    def report_success(self):
        with self.lock:
            self.consecutive_success += 1
            if self.consecutive_success >= 3:
                # Slowly reduce cooldown
                self.cooldown_duration = max(0, self.cooldown_duration - 1)
                self.consecutive_success = 0

RATE_LIMITER = RateLimiter()

def _save_cache(model, prompt, resp_content, resp_type, resp, message=None, log_title="default"):
    with LOCK:
        logs = []
        file = os.path.join(GPT_LOG_FOLDER, f"{log_title}.json")
        os.makedirs(os.path.dirname(file), exist_ok=True)
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        logs.append({"model": model, "prompt": prompt, "resp_content": resp_content, "resp_type": resp_type, "resp": resp, "message": message})
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=4)

def _load_cache(prompt, resp_type, log_title):
    with LOCK:
        file = os.path.join(GPT_LOG_FOLDER, f"{log_title}.json")
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    if item["prompt"] == prompt and item["resp_type"] == resp_type:
                        return item["resp"]
        return False

# ------------
# ask gpt once
# ------------

@except_handler("GPT request failed", retry=5)
def ask_gpt(prompt, resp_type=None, valid_def=None, log_title="default"):
    if not load_key("api.key"):
        raise ValueError("API key is not set")
    
    # check cache
    cached = _load_cache(prompt, resp_type, log_title)
    if cached:
        vprint("use cache response")
        return cached

    RATE_LIMITER.wait_if_needed()

    model = load_key("api.model")
    base_url = load_key("api.base_url")
    if 'ark' in base_url:
        base_url = "https://ark.cn-beijing.volces.com/api/v3" # huoshan base url
    elif 'v1' not in base_url:
        base_url = base_url.strip('/') + '/v1'
    client = OpenAI(api_key=load_key("api.key"), base_url=base_url)
    response_format = {"type": "json_object"} if resp_type == "json" and load_key("api.llm_support_json") else None

    messages = [{"role": "user", "content": prompt}]

    params = dict(
        model=model,
        messages=messages,
        response_format=response_format,
        timeout=300
    )
    start_time = time.time()
    try:
        resp_raw = client.chat.completions.create(**params)
        RATE_LIMITER.report_success()
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            RATE_LIMITER.report_error(is_429=True)
        raise e
    duration = time.time() - start_time
    
    log_api_call("GPT", model, params, resp_raw.choices[0].message.content, duration)

    # process and return full result
    resp_content = resp_raw.choices[0].message.content
    if resp_type == "json":
        resp = json_repair.loads(resp_content)
    else:
        resp = resp_content
    
    # check if the response format is valid
    if valid_def:
        valid_resp = valid_def(resp)
        if valid_resp['status'] != 'success':
            _save_cache(model, prompt, resp_content, resp_type, resp, log_title="error", message=valid_resp['message'])
            raise ValueError(f"❎ API response error: {valid_resp['message']}")

    _save_cache(model, prompt, resp_content, resp_type, resp, log_title=log_title)
    return resp


if __name__ == '__main__':
    from rich import print as rprint
    
    result = ask_gpt("""test respond ```json\n{\"code\": 200, \"message\": \"success\"}\n```""", resp_type="json")
    vprint(f"Test json output result: {result}")
