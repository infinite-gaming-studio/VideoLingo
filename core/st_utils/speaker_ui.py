import streamlit as st
import os
import pandas as pd
from core.utils.models import _8_1_AUDIO_TASK, _AUDIO_REFERS_DIR, _6_ALIGNED_FOR_AUDIO
from core.utils.config_utils import load_key
from core.utils.speaker_utils import extract_speaker_snippets, get_speaker_profiles, save_speaker_mappings, load_speaker_mappings, get_voice_list
from translations.translations import translate as t

def speaker_configuration_ui():
    """Display an interactive speaker-to-voice configuration table in the main area."""
    if not load_key("whisper.diarization"):
        return True # Continue if diarization is disabled

    if not os.path.exists(_6_ALIGNED_FOR_AUDIO):
        return False # Need alignment first
        
    st.subheader(t("Speaker Voice Configuration"))
    
    # Ensure snippets and profiles are ready
    if not os.path.exists(_AUDIO_REFERS_DIR) or not os.listdir(_AUDIO_REFERS_DIR):
        with st.spinner(t("Extracting speaker snippets...")):
            extract_speaker_snippets()
            
    # Load or generate profiles
    if 'speaker_profiles' not in st.session_state:
        with st.spinner(t("Analyzing speaker profiles...")):
            st.session_state.speaker_profiles = get_speaker_profiles()
    
    profiles = st.session_state.speaker_profiles
    existing_mappings = load_speaker_mappings()
    
    df_aligned = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    unique_speakers = sorted(df_aligned['speaker_id'].dropna().unique())
    
    if not unique_speakers:
        return True # No speakers detected

    tts_method = load_key("tts_method")
    voice_options = get_voice_list(tts_method)
    
    new_mappings = {}
    
    # Display as a table-like structure
    for speaker in unique_speakers:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([1, 2, 2, 3])
            
            with col1:
                st.write(f"**{speaker}**")
            
            with col2:
                audio_path = os.path.join(_AUDIO_REFERS_DIR, f"{speaker}.mp3")
                if os.path.exists(audio_path):
                    st.audio(audio_path)
                else:
                    st.warning("No sample")
            
            with col3:
                profile = profiles.get(speaker, {})
                rec_voice = profile.get("recommended_voice", "N/A")
                st.write(f"AI: {profile.get('gender', '?')}, {profile.get('tone', '?')}")
                st.caption(f"Choice: {rec_voice}")
            
            with col4:
                default_voice = existing_mappings.get(speaker, rec_voice if rec_voice in voice_options else voice_options[0] if voice_options else "")
                selected = st.selectbox(
                    t("Select Voice"), 
                    options=voice_options, 
                    index=voice_options.index(default_voice) if default_voice in voice_options else 0,
                    key=f"select_{speaker}"
                )
                new_mappings[speaker] = selected

    if st.button(t("Confirm Speaker Configurations"), key="confirm_speaker_configs"):
        save_speaker_mappings(new_mappings)
        st.success(t("Speaker configurations saved!"))
        st.session_state.speaker_confirmed = True
        st.rerun()
    
    return st.session_state.get('speaker_confirmed', False) or os.path.exists("output/log/speaker_mappings.json")
