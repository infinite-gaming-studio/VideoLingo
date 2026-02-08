import streamlit as st
from translations.translations import translate as t
from translations.translations import DISPLAY_LANGUAGES
import json
import yaml as pyyaml # For safe dumping logic if needed
from ruamel.yaml import YAML
import time
from core.utils import *

def config_input(label, key, help=None):
    """Generic config input handler"""
    val = st.text_input(label, value=load_key(key), help=help)
    if val != load_key(key):
        update_key(key, val)
    return val

def page_setting():
    
    # Config Management
    with st.expander(t("Config Management"), expanded=False):
        # 1. Export Section
        st.subheader(t("Export Config"))
        try:
            SIDEBAR_KEYS = [
                "display_language",
                "api.key", "api.base_url", "api.model", "api.llm_support_json",
                "whisper.language", "whisper.runtime", "whisper.elevenlabs_api_key", "whisper.diarization",
                "whisper.min_speakers", "whisper.max_speakers",
                "cloud_native.cloud_url", "cloud_native.token",
                "target_language", "demucs", "burn_subtitles", "tts_method",
                "sf_fish_tts.api_key", "sf_fish_tts.mode", "sf_fish_tts.voice",
                "openai_tts.api_key", "openai_tts.voice",
                "fish_tts.api_key", "fish_tts.character",
                "azure_tts.api_key", "azure_tts.voice",
                "azure_tts.api_key", "azure_tts.voice",
                "gpt_sovits.character", "gpt_sovits.refer_mode",
                "edge_tts.voice", "sf_cosyvoice2.api_key", "f5tts.302_api"
            ]

            partial_config = {}
            for key in SIDEBAR_KEYS:
                try:
                    val = load_key(key)
                    keys = key.split('.')
                    curr = partial_config
                    for k in keys[:-1]:
                        if k not in curr: curr[k] = {}
                        curr = curr[k]
                    curr[keys[-1]] = val
                except: pass

            # Export as YAML (preferred) or JSON
            from io import StringIO
            yaml = YAML()
            stream = StringIO()
            yaml.dump(partial_config, stream)
            yaml_output = stream.getvalue()
            
            st.download_button(
                label=t("Export as YAML (.yaml) ⬇️"),
                data=yaml_output,
                file_name="videolingo_config.yaml",
                mime="text/yaml",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Export failed: {e}")

        st.divider()

        # 2. Import Section
        st.subheader(t("Import Config"))
        uploaded_file = st.file_uploader(t("Upload Config File"), type=["json", "yaml", "yml"], help=t("Support .yaml, .yml, or .json files"))
        
        if uploaded_file is not None:
            # Preview and Confirm logic
            file_type = uploaded_file.name.split('.')[-1].lower()
            try:
                if file_type == 'json':
                    new_config = json.load(uploaded_file)
                else:
                    yaml_loader = YAML()
                    new_config = yaml_loader.load(uploaded_file)
                
                if st.button(t("✅ Confirm Import"), use_container_width=True, type="primary"):
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    with open('config.yaml', 'r', encoding='utf-8') as f:
                        current_config = yaml.load(f)
                    
                    def recursive_update(d, u):
                        for k, v in u.items():
                            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                                recursive_update(d[k], v)
                            else:
                                d[k] = v
                        return d
                    
                    updated_config = recursive_update(current_config, new_config)
                    
                    with open('config.yaml', 'w', encoding='utf-8') as f:
                        yaml.dump(updated_config, f)
                        
                    st.success(t("Config imported successfully!"))
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to parse file: {e}")

    display_language = st.selectbox("Display Language 🌐", 
                                  options=list(DISPLAY_LANGUAGES.keys()),
                                  index=list(DISPLAY_LANGUAGES.values()).index(load_key("display_language")))
    if DISPLAY_LANGUAGES[display_language] != load_key("display_language"):
        update_key("display_language", DISPLAY_LANGUAGES[display_language])
        st.rerun()

    # with st.expander(t("Youtube Settings"), expanded=True):
    #     config_input(t("Cookies Path"), "youtube.cookies_path")

    with st.expander(t("LLM Configuration"), expanded=True):
        config_input(t("API_KEY"), "api.key")
        config_input(t("BASE_URL"), "api.base_url", help=t("Openai format, will add /v1/chat/completions automatically"))
        
        config_input(t("MODEL"), "api.model", help=t("click to check API validity"))
        if st.button(t("🔄 Verify API"), key="api", use_container_width=True):
            st.toast(t("API Key is valid") if check_api() else t("API Key is invalid"), 
                    icon="✅" if check_api() else "❌")
        llm_support_json = st.toggle(t("LLM JSON Format Support"), value=load_key("api.llm_support_json"), help=t("Enable if your LLM supports JSON mode output"))
        if llm_support_json != load_key("api.llm_support_json"):
            update_key("api.llm_support_json", llm_support_json)
            st.rerun()
            
        debug_mode = st.toggle(t("Debug Mode"), value=load_key("debug"), help=t("Enable detailed logging for debugging"))
        if debug_mode != load_key("debug"):
            update_key("debug", debug_mode)
            st.rerun()
    with st.expander(t("Subtitles Settings"), expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            langs = {
                "🇺🇸 English": "en",
                "🇨🇳 简体中文": "zh",
                "🇪🇸 Español": "es",
                "🇷🇺 Русский": "ru",
                "🇫🇷 Français": "fr",
                "🇩🇪 Deutsch": "de",
                "🇮🇹 Italiano": "it",
                "🇯🇵 日本語": "ja"
            }
            lang = st.selectbox(
                t("Recog Lang"),
                options=list(langs.keys()),
                index=list(langs.values()).index(load_key("whisper.language"))
            )
            if langs[lang] != load_key("whisper.language"):
                update_key("whisper.language", langs[lang])
                st.rerun()

        runtime = st.selectbox(t("WhisperX Runtime"), options=["cloud", "elevenlabs"], index=["cloud", "elevenlabs"].index(load_key("whisper.runtime")), help=t("Cloud runtime requires 302ai API key, elevenlabs runtime requires ElevenLabs API key"))
        if runtime != load_key("whisper.runtime"):
            update_key("whisper.runtime", runtime)
            st.rerun()

        if runtime == "elevenlabs":
            config_input(("ElevenLabs API"), "whisper.elevenlabs_api_key")

        with c2:
            target_language = st.text_input(t("Target Lang"), value=load_key("target_language"), help=t("Input any language in natural language, as long as llm can understand"))
            if target_language != load_key("target_language"):
                update_key("target_language", target_language)
                st.rerun()

        demucs = st.toggle(t("Vocal separation enhance"), value=load_key("demucs"), help=t("Recommended for videos with loud background noise, but will increase processing time"))
        if demucs != load_key("demucs"):
            update_key("demucs", demucs)
            st.rerun()

        burn_subtitles = st.toggle(t("Burn-in Subtitles"), value=load_key("burn_subtitles"), help=t("Whether to burn subtitles into the video, will increase processing time"))
        if burn_subtitles != load_key("burn_subtitles"):
            update_key("burn_subtitles", burn_subtitles)
            st.rerun()

        diarization = st.toggle(t("Speaker Diarization"), value=load_key("whisper.diarization"), help=t("Enable speaker diarization (multi-role detection). Cloud runtime only."))
        if diarization != load_key("whisper.diarization"):
            update_key("whisper.diarization", diarization)
            st.rerun()
        
        if diarization:
            c_min, c_max = st.columns(2)
            with c_min:
                # Default to 2 for min_speakers to allow flexibility in detection
                current_min = load_key("whisper.min_speakers")
                if current_min is None or current_min == 0:
                    current_min = 2  # Default: at least 2 speakers for multi-speaker scenarios
                min_s = st.number_input(t("Min Speakers"), value=int(current_min), min_value=1, max_value=20, step=1, help=t("Minimum number of speakers to detect. For movies/conversations, set to 2."))
                if min_s != load_key("whisper.min_speakers"):
                    update_key("whisper.min_speakers", min_s)
                    st.rerun()
            with c_max:
                # Default to 6 for max_speakers to capture more speakers in complex scenarios
                current_max = load_key("whisper.max_speakers")
                if current_max is None or current_max == 0:
                    current_max = 6  # Default: up to 6 speakers
                max_s = st.number_input(t("Max Speakers"), value=int(current_max), min_value=1, max_value=20, step=1, help=t("Maximum number of speakers to detect. For movies with many characters, set higher (6-10)."))
                if max_s != load_key("whisper.max_speakers"):
                    update_key("whisper.max_speakers", max_s)
                    st.rerun()
            
            # Add helpful guidance
            st.info("💡 **提示**：对于电影或多人对话场景，建议设置 min=2, max=6-10。识别后可在下一步合并重复角色。")

        # Show cloud settings only if cloud runtime is selected
        if runtime == "cloud":
            with st.container(border=True):
                st.write(f"🌐 {t('Cloud Service Settings')}")
                config_input(t("Cloud Service URL"), "cloud_native.cloud_url", help=t("URL for both WhisperX and Demucs cloud services"))
                config_input(t("Authentication Token"), "cloud_native.token", help=t("Token for cloud services authentication"))
    with st.expander(t("Dubbing Settings"), expanded=True):
        tts_methods = ["azure_tts", "openai_tts", "fish_tts", "sf_fish_tts", "edge_tts", "gpt_sovits", "custom_tts", "sf_cosyvoice2", "f5tts"]
        select_tts = st.selectbox(t("TTS Method"), options=tts_methods, index=tts_methods.index(load_key("tts_method")))
        if select_tts != load_key("tts_method"):
            update_key("tts_method", select_tts)
            st.rerun()

        # sub settings for each tts method
        if select_tts == "sf_fish_tts":
            config_input(t("SiliconFlow API Key"), "sf_fish_tts.api_key")
            
            # Add mode selection dropdown
            mode_options = {
                "preset": t("Preset"),
                "custom": t("Refer_stable"),
                "dynamic": t("Refer_dynamic")
            }
            selected_mode = st.selectbox(
                t("Mode Selection"),
                options=list(mode_options.keys()),
                format_func=lambda x: mode_options[x],
                index=list(mode_options.keys()).index(load_key("sf_fish_tts.mode")) if load_key("sf_fish_tts.mode") in mode_options.keys() else 0
            )
            if selected_mode != load_key("sf_fish_tts.mode"):
                update_key("sf_fish_tts.mode", selected_mode)
                st.rerun()
            if selected_mode == "preset":
                config_input("Voice", "sf_fish_tts.voice")

        elif select_tts == "openai_tts":
            config_input("302ai API", "openai_tts.api_key")
            config_input(t("OpenAI Voice"), "openai_tts.voice")

        elif select_tts == "fish_tts":
            config_input("302ai API", "fish_tts.api_key")
            fish_tts_character = st.selectbox(t("Fish TTS Character"), options=list(load_key("fish_tts.character_id_dict").keys()), index=list(load_key("fish_tts.character_id_dict").keys()).index(load_key("fish_tts.character")))
            if fish_tts_character != load_key("fish_tts.character"):
                update_key("fish_tts.character", fish_tts_character)
                st.rerun()

        elif select_tts == "azure_tts":
            config_input("302ai API", "azure_tts.api_key")
            config_input(t("Azure Voice"), "azure_tts.voice")
        
        elif select_tts == "gpt_sovits":
            st.info(t("Please refer to Github homepage for GPT_SoVITS configuration"))
            config_input(t("SoVITS Character"), "gpt_sovits.character")
            
            refer_mode_options = {1: t("Mode 1: Use provided reference audio only"), 2: t("Mode 2: Use first audio from video as reference"), 3: t("Mode 3: Use each audio from video as reference")}
            selected_refer_mode = st.selectbox(
                t("Refer Mode"),
                options=list(refer_mode_options.keys()),
                format_func=lambda x: refer_mode_options[x],
                index=list(refer_mode_options.keys()).index(load_key("gpt_sovits.refer_mode")),
                help=t("Configure reference audio mode for GPT-SoVITS")
            )
            if selected_refer_mode != load_key("gpt_sovits.refer_mode"):
                update_key("gpt_sovits.refer_mode", selected_refer_mode)
                st.rerun()
                
        elif select_tts == "edge_tts":
            config_input(t("Edge TTS Voice"), "edge_tts.voice")

        elif select_tts == "sf_cosyvoice2":
            config_input(t("SiliconFlow API Key"), "sf_cosyvoice2.api_key")
        
        elif select_tts == "f5tts":
            config_input("302ai API", "f5tts.302_api")
        
def check_api():
    try:
        resp = ask_gpt("This is a test, response 'message':'success' in json format.", 
                      resp_type="json", log_title='None')
        return resp.get('message') == 'success'
    except Exception:
        return False
    
if __name__ == "__main__":
    check_api()
