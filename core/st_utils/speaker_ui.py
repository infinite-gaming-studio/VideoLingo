import streamlit as st
import os
import pandas as pd
import json
from datetime import timedelta
from core.utils.models import _8_1_AUDIO_TASK, _AUDIO_REFERS_DIR, _6_ALIGNED_FOR_AUDIO
from core.utils.config_utils import load_key
from core.utils.speaker_utils import (
    extract_speaker_snippets, get_speaker_profiles, save_speaker_mappings, 
    load_speaker_mappings, get_voice_list, merge_speakers, split_speaker_by_time
)
from translations.translations import translate as t

def speaker_configuration_ui():
    """Display an interactive speaker-to-voice configuration table in the main area.
    
    Enhanced with speaker merging/splitting capabilities for better handling of
    multi-speaker scenarios like movies and conversations.
    """
    if not load_key("whisper.diarization"):
        return True  # Continue if diarization is disabled

    if not os.path.exists(_6_ALIGNED_FOR_AUDIO):
        return False  # Need alignment first
    
    st.subheader(t("Speaker Voice Configuration"))
    
    # Load data
    df_aligned = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    
    # Check if speaker_id column exists
    if 'speaker_id' not in df_aligned.columns:
        st.warning("⚠️ 角色识别已启用，但未检测到角色信息。请检查音频质量或关闭角色识别。")
        return True
    
    # Handle speaker modifications (merge/split)
    if handle_speaker_modifications(df_aligned):
        # Data was modified, reload
        df_aligned = pd.read_excel(_6_ALIGNED_FOR_AUDIO)
    
    unique_speakers = sorted(df_aligned['speaker_id'].dropna().unique())
    
    if not unique_speakers:
        st.warning("⚠️ 未检测到任何角色。请检查音频是否包含多人对话，或关闭角色识别。")
        return True
    
    # Show speaker timeline visualization
    with st.expander("📊 查看说话者时间轴分布", expanded=False):
        display_speaker_timeline(df_aligned)
    
    # Show speaker management tools
    with st.expander("🔧 说话者管理工具", expanded=False):
        display_speaker_management_tools(df_aligned, unique_speakers)
    
    # Clean up old mappings if speakers don't match (new video uploaded)
    existing_mappings = load_speaker_mappings()
    if existing_mappings:
        old_speakers = set(existing_mappings.keys())
        current_speakers = set(unique_speakers)
        if old_speakers != current_speakers:
            st.info("🔄 检测到新视频，已重置角色语音配置")
            save_speaker_mappings({})
            existing_mappings = {}
            if 'speaker_confirmed' in st.session_state:
                del st.session_state['speaker_confirmed']
    
    # Ensure snippets and profiles are ready
    if not os.path.exists(_AUDIO_REFERS_DIR) or not os.listdir(_AUDIO_REFERS_DIR):
        with st.spinner(t("Extracting speaker snippets...")):
            extract_speaker_snippets()
    
    # Load or generate profiles
    if 'speaker_profiles' not in st.session_state:
        with st.spinner(t("Analyzing speaker profiles...")):
            st.session_state.speaker_profiles = get_speaker_profiles()
    
    profiles = st.session_state.speaker_profiles
    
    tts_method = load_key("tts_method")
    voice_options = get_voice_list(tts_method)
    
    new_mappings = {}
    
    # Display speaker configuration table
    st.markdown("### 🎭 角色配置")
    st.info("💡 提示：先听每个角色的音频样本，确认是否为同一人。如果多个角色实际上是同一人，请使用上方的『说话者管理工具』进行合并。")
    
    for speaker in unique_speakers:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([1, 2, 2, 3])
            
            with col1:
                st.write(f"**{speaker}**")
                # Show line count for this speaker
                line_count = len(df_aligned[df_aligned['speaker_id'] == speaker])
                st.caption(f"{line_count} 句台词")
            
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
    
    if st.button(t("Confirm Speaker Configurations"), key="confirm_speaker_configs", type="primary"):
        save_speaker_mappings(new_mappings)
        st.success(t("Speaker configurations saved!"))
        st.session_state.speaker_confirmed = True
        st.rerun()
    
    return st.session_state.get('speaker_confirmed', False) or os.path.exists("output/log/speaker_mappings.json")


def handle_speaker_modifications(df_aligned):
    """Handle any pending speaker modifications from session state.
    
    Returns True if data was modified and needs reload.
    """
    modified = False
    
    # Handle merge operation
    if 'pending_merge' in st.session_state:
        speakers_to_merge = st.session_state.pop('pending_merge')
        if len(speakers_to_merge) >= 2:
            with st.spinner("🔄 正在合并说话者..."):
                merge_speakers(df_aligned, speakers_to_merge)
                st.success(f"✅ 已合并 {len(speakers_to_merge)} 个说话者")
                # Clear snippets to force regeneration
                if os.path.exists(_AUDIO_REFERS_DIR):
                    import shutil
                    shutil.rmtree(_AUDIO_REFERS_DIR)
                if 'speaker_profiles' in st.session_state:
                    del st.session_state['speaker_profiles']
                modified = True
    
    # Handle split operation
    if 'pending_split' in st.session_state:
        split_info = st.session_state.pop('pending_split')
        speaker_to_split = split_info['speaker']
        split_points = split_info['points']
        with st.spinner("✂️ 正在拆分说话者..."):
            split_speaker_by_time(df_aligned, speaker_to_split, split_points)
            st.success(f"✅ 已将 {speaker_to_split} 拆分为 {len(split_points) + 1} 个角色")
            # Clear snippets to force regeneration
            if os.path.exists(_AUDIO_REFERS_DIR):
                import shutil
                shutil.rmtree(_AUDIO_REFERS_DIR)
            if 'speaker_profiles' in st.session_state:
                del st.session_state['speaker_profiles']
            modified = True
    
    return modified


def display_speaker_timeline(df_aligned):
    """Display a visual timeline showing when each speaker appears in the video."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    
    if 'timestamp' not in df_aligned.columns:
        st.warning("时间戳信息不可用")
        return
    
    # Parse timestamps
    def parse_timestamp(ts_str):
        """Parse timestamp string like '00:00:01,000 --> 00:00:05,000' to seconds."""
        try:
            start_str = ts_str.split(' --> ')[0]
            parts = start_str.replace(',', '.').split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except:
            return 0
    
    df_aligned['start_sec'] = df_aligned['timestamp'].apply(parse_timestamp)
    
    # Get unique speakers and assign colors
    unique_speakers = sorted(df_aligned['speaker_id'].dropna().unique())
    colors = plt.cm.Set3(range(len(unique_speakers)))
    speaker_colors = {spk: colors[i] for i, spk in enumerate(unique_speakers)}
    
    # Create timeline plot
    fig, ax = plt.subplots(figsize=(12, max(4, len(unique_speakers) * 0.8)))
    
    max_time = df_aligned['start_sec'].max()
    
    for idx, speaker in enumerate(unique_speakers):
        speaker_data = df_aligned[df_aligned['speaker_id'] == speaker]
        for _, row in speaker_data.iterrows():
            start = row['start_sec']
            duration = 2  # Assume 2 seconds per line for visualization
            ax.barh(idx, duration, left=start, height=0.6, 
                   color=speaker_colors[speaker], alpha=0.7)
    
    ax.set_yticks(range(len(unique_speakers)))
    ax.set_yticklabels(unique_speakers)
    ax.set_xlabel('Time (seconds)')
    ax.set_title('Speaker Timeline Distribution')
    ax.set_xlim(0, max_time + 10)
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    st.pyplot(fig)
    
    # Show statistics
    st.markdown("#### 📈 说话者统计")
    stats_cols = st.columns(len(unique_speakers))
    for idx, speaker in enumerate(unique_speakers):
        speaker_data = df_aligned[df_aligned['speaker_id'] == speaker]
        with stats_cols[idx]:
            st.metric(
                label=speaker,
                value=f"{len(speaker_data)} 句",
                delta=f"{speaker_data['start_sec'].min():.0f}s - {speaker_data['start_sec'].max():.0f}s"
            )


def display_speaker_management_tools(df_aligned, unique_speakers):
    """Display tools for merging and splitting speakers."""
    
    # Merge speakers section
    st.markdown("#### 🔀 合并说话者")
    st.caption("如果系统错误地将同一人识别为多个角色，请选择要合并的角色")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        speakers_to_merge = st.multiselect(
            "选择要合并的角色（选择2个或更多）",
            options=unique_speakers,
            key="merge_select"
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("🔄 合并", disabled=len(speakers_to_merge) < 2, key="merge_btn"):
            st.session_state['pending_merge'] = speakers_to_merge
            st.rerun()
    
    if len(speakers_to_merge) >= 2:
        st.info(f"将合并: {', '.join(speakers_to_merge)} → 保留为 {speakers_to_merge[0]}")
    
    st.divider()
    
    # Split speaker section
    st.markdown("#### ✂️ 拆分说话者")
    st.caption("如果系统错误地将多个人的对话合并为一个角色，可在此拆分")
    
    if len(unique_speakers) > 0:
        col3, col4 = st.columns([2, 2])
        with col3:
            speaker_to_split = st.selectbox(
                "选择要拆分的角色",
                options=unique_speakers,
                key="split_select"
            )
        
        with col4:
            # Get timestamps for this speaker
            speaker_data = df_aligned[df_aligned['speaker_id'] == speaker_to_split]
            st.caption(f"该角色共有 {len(speaker_data)} 句台词")
            
            # Allow selecting split points
            split_points_str = st.text_input(
                "输入拆分时间点（秒，逗号分隔，如: 30,60,90）",
                placeholder="例如: 30,60",
                key="split_points"
            )
            
            if st.button("✂️ 拆分", disabled=not split_points_str.strip(), key="split_btn"):
                try:
                    split_points = [float(x.strip()) for x in split_points_str.split(',')]
                    st.session_state['pending_split'] = {
                        'speaker': speaker_to_split,
                        'points': sorted(split_points)
                    }
                    st.rerun()
                except ValueError:
                    st.error("❌ 时间格式错误，请输入数字（如: 30,60）")
