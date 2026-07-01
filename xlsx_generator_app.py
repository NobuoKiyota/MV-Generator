import streamlit as st
import os
import pandas as pd
import tempfile
from utils import analyze_audio, generate_initial_timeline, parse_tagged_lyrics, export_project_xlsx

st.set_page_config(page_title="楽曲演出コンテ自動生成ツール", layout="centered")

# セッション状態の初期化
if "xlsx_timeline_data" not in st.session_state:
    st.session_state.xlsx_timeline_data = None
if "xlsx_result_summary" not in st.session_state:
    st.session_state.xlsx_result_summary = None
if "xlsx_bpm" not in st.session_state:
    st.session_state.xlsx_bpm = ""
if "xlsx_duration" not in st.session_state:
    st.session_state.xlsx_duration = 180.0
if "xlsx_lyrics" not in st.session_state:
    st.session_state.xlsx_lyrics = ""
if "xlsx_audio_path" not in st.session_state:
    st.session_state.xlsx_audio_path = None
if "xlsx_result_bpm" not in st.session_state:
    st.session_state.xlsx_result_bpm = 120.0

st.title("📊 楽曲演出コンテ自動生成 ＆ Excel (xlsx) 化ツール")
st.markdown("音源と最低限の入力から、AIが世界観・演出ルール・カット割り・画像プロンプトの初稿を全自動で組み立てて Excel に出力します。")

st.markdown("---")
st.header("🎵 1. 音源と基本情報の入力")

# 音源ファイル
audio_file = st.file_uploader("音源ファイルをアップロード", type=["mp3", "wav", "m4a", "ogg"])
if audio_file is not None:
    # 一時保存
    temp_dir = tempfile.gettempdir()
    saved_audio_path = os.path.join(temp_dir, f"xlsx_audio_{audio_file.name}")
    with open(saved_audio_path, "wb") as f:
        f.write(audio_file.getbuffer())
    st.session_state.xlsx_audio_path = saved_audio_path

# 音源タイプ (Vocal / Instrumental)
audio_type = st.radio(
    "音源のタイプ",
    options=["歌詞もの (Vocal)", "インスト (Instrumental)"],
    index=0 if "xlsx_audio_type" not in st.session_state or st.session_state.xlsx_audio_type == "vocal" else 1,
    horizontal=True,
    help="インストを選択すると、歌詞入力エリアが無効（グレーアウト）になります。"
)
st.session_state.xlsx_audio_type = "vocal" if "Vocal" in audio_type else "inst"

# 歌詞入力
is_vocal = st.session_state.xlsx_audio_type == "vocal"
lyrics_placeholder = "例:\n[Intro]\n(インスト)\n\n[Verse 1]\n夜の街を歩く君の影...\n\n[Chorus]\n光る星を見上げて叫ぶよ..."
lyrics_val = st.text_area(
    "歌詞情報 (セクションタグ付き)",
    value=st.session_state.xlsx_lyrics if is_vocal else "",
    placeholder=lyrics_placeholder if is_vocal else "(インスト選択中のため入力不可)",
    disabled=not is_vocal,
    height=200,
    help="[Intro] や [Chorus] などのタグを付けることで、セクションの構成に同期させます。"
)
if is_vocal:
    st.session_state.xlsx_lyrics = lyrics_val

# 歌詞セクションのプレビュー
if is_vocal and st.session_state.xlsx_lyrics:
    parsed = parse_tagged_lyrics(st.session_state.xlsx_lyrics)
    if parsed:
        with st.expander("🔍 検出されたセクション（プレビュー）", expanded=False):
            for item in parsed:
                sec = item['section']
                lyr = item['lyrics'].strip().replace('\n', ' / ')
                preview = lyr[:40] + "..." if len(lyr) > 40 else lyr
                st.write(f"**🔷 {sec}**: *{preview}*")

# テンポ（BPM）とオフセット
col_bpm, col_offset = st.columns(2)
with col_bpm:
    bpm_val = st.text_input(
        "BPM (テンポ)",
        value=st.session_state.xlsx_bpm,
        placeholder="空欄時は音源から自動検出",
        help="テンポを指定します。空欄の場合は音源ファイルから自動検出します。"
    )
    st.session_state.xlsx_bpm = bpm_val
with col_offset:
    offset_val = st.number_input(
        "1小節目の開始時間 (秒)",
        min_value=0.0,
        value=st.session_state.get("xlsx_first_bar_offset", 0.0),
        step=0.1,
        format="%.3f",
        help="曲が始まる最初の小節の頭（秒）を指定します。これ以降にBPMに基づいた小節線が計算されます。"
    )
    st.session_state.xlsx_first_bar_offset = offset_val

# 🛠️ 詳細設定 (Advanced Settings)
with st.expander("🛠️ 詳細設定 (Advanced Settings)"):
    time_sig = st.selectbox(
        "拍子 (Time Signature)",
        options=["4/4", "3/4", "6/8", "2/4"],
        index=0,
        help="BPMと1小節目開始時間から小節の長さを計算するために使用します。"
    )
    split_unit = st.selectbox(
        "タイムラインの分割単位",
        options=["4小節ごと", "2小節ごと", "8小節ごと", "セクションごと"],
        index=0,
        help="Excelのタイムライン分割の細かさを指定します。"
    )
    vis_style = st.selectbox(
        "ビジュアルスタイル",
        options=["特になし", "シネマティック (Cinematic)", "アニメ風 (Anime style)", "サイバーパンク (Cyberpunk)", "水彩画風 (Watercolor)", "3D CG", "ピクセルアート (Pixel art)"],
        index=0,
        help="生成される画像プロンプトに共通の画風スタイルを反映させます。"
    )
    aspect_ratio = st.selectbox(
        "アスペクト比",
        options=["16:9", "9:16", "1:1"],
        index=0,
        help="出力画像の比率に合わせたプロンプト補正を行います。"
    )

st.markdown("---")
st.header("🔑 2. API設定と実行")

# APIキー入力
api_key_input = st.text_input(
    "Gemini API Key",
    type="password",
    value=os.environ.get("GEMINI_API_KEY", ""),
    help="APIキーを入力するか、プロジェクトの.envファイルにGEMINI_API_KEYを設定してください。"
)

# 解析と生成の実行ボタン
if st.button("🎵 演出コンテ ＆ プロンプト自動生成", use_container_width=True):
    api_key = api_key_input if api_key_input else os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("Gemini API Keyが設定されていません。")
    else:
        with st.spinner("音源のテンポと長さを解析中..."):
            bpm = 120.0
            duration = 180.0
            
            # 音源がアップロードされていて、BPMまたは長さの自動解析が必要な場合
            if st.session_state.xlsx_audio_path:
                try:
                    analysis = analyze_audio(st.session_state.xlsx_audio_path)
                    if analysis:
                        duration = analysis["duration"]
                        # BPMの指定がない場合のみ、自動検出値を使用
                        if not st.session_state.xlsx_bpm.strip():
                            bpm = analysis["bpm"]
                        else:
                            bpm = float(st.session_state.xlsx_bpm)
                        st.info(f"🔊 音源解析完了: 自動検出された曲の長さ: {duration:.2f}秒, 解析BPM: {analysis['bpm']}")
                    else:
                        st.warning("音源解析に失敗しました。デフォルト設定（BPM=120.0, 長さ=180.0秒）で実行します。")
                except Exception as e:
                    st.error(f"音源解析エラー: {e}")
            else:
                if st.session_state.xlsx_bpm.strip():
                    try:
                        bpm = float(st.session_state.xlsx_bpm)
                    except ValueError:
                        st.warning("指定されたBPMが無効なため、デフォルト値 120.0 を使用します。")
                st.info("💡 音源ファイルなし: デフォルトの長さ 180.0 秒、および指定/デフォルトのBPMを使用します。")

            st.session_state.xlsx_duration = duration

            # AIによるタイムライン生成
            with st.spinner("Gemini が世界観・演出プロット・タイムライン・プロンプトを全自動生成中..."):
                try:
                    # 歌詞ものかインストかで歌詞パラメータを調整
                    lyrics_to_send = st.session_state.xlsx_lyrics if is_vocal else ""
                    
                    timeline_result = generate_initial_timeline(
                        lyrics=lyrics_to_send,
                        bpm=bpm,
                        duration=duration,
                        core_concept="", # AIに自動生成させるため空で渡す
                        global_rules="", # AIに自動生成させるため空で渡す
                        section_rules="", # AIに自動生成させるため空で渡す
                        keywords="", # AIに自動生成させるため空で渡す
                        api_key=api_key,
                        first_bar_offset=st.session_state.xlsx_first_bar_offset,
                        time_signature=time_sig,
                        split_unit=split_unit,
                        visual_style=vis_style,
                        aspect_ratio=aspect_ratio
                    )
                    
                    if timeline_result and "timeline" in timeline_result:
                        st.session_state.xlsx_timeline_data = timeline_result["timeline"]
                        st.session_state.xlsx_result_summary = timeline_result.get("summary", {})
                        st.session_state.xlsx_result_bpm = timeline_result.get("bpm", bpm)
                        st.success("🎉 演出コンテの自動生成が完了しました！")
                    else:
                        st.error("演出コンテの生成結果が不正です。")
                except Exception as e:
                    st.error(f"演出コンテ生成エラー: {e}")

# 結果表示とダウンロード
if st.session_state.xlsx_timeline_data:
    st.markdown("---")
    st.header("📊 生成された演出コンテのプレビュー")
    
    # 概要設定の表示
    summary = st.session_state.xlsx_result_summary
    if summary:
        with st.expander("🔍 AIが自動設計した世界観・コンセプト設定", expanded=True):
            st.write(f"**🎵 提案タイトル**: {summary.get('title', '無題')}")
            st.write(f"**🌟 世界観・コンセプト**: {summary.get('concept', '')}")
            st.write(f"**👥 キャラクター設定**: {summary.get('characters', '')}")
            st.write(f"**📋 全体の演出ルール**: {summary.get('rules', '')}")
            
    # タイムラインプレビュー用のデータフレーム作成
    preview_rows = []
    for i, item in enumerate(st.session_state.xlsx_timeline_data):
        preview_rows.append({
            "Cut": i + 1,
            "Section": item.get("section", ""),
            "Start (秒)": item.get("start_time", 0.0),
            "End (秒)": item.get("end_time", 0.0),
            "歌詞": item.get("lyrics", ""),
            "演出・カメラワーク": item.get("description", ""),
            "画像プロンプト": item.get("prompt", "")
        })
    df_preview = pd.DataFrame(preview_rows)
    st.dataframe(df_preview, use_container_width=True)

    # Excelエクスポート処理
    st.subheader("📥 Excelファイルダウンロード")
    
    try:
        # AIが自動生成した世界観やキャラクター設定を引き継ぐ
        core_concept_text = ""
        global_rules_text = ""
        
        if summary:
            core_concept_text = f"【世界観・コンセプト】\n{summary.get('concept', '')}\n\n【キャラクター設定】\n{summary.get('characters', '')}"
            global_rules_text = summary.get('rules', '')
            
        project_title = summary.get('title', 'my_song_project') if summary else "my_song_project"
        
        xlsx_bytes = export_project_xlsx(
            project_name=project_title,
            timeline_data=st.session_state.xlsx_timeline_data,
            bpm=st.session_state.xlsx_result_bpm,
            duration=st.session_state.xlsx_duration,
            core_concept=core_concept_text,
            global_rules=global_rules_text,
            first_bar_offset=st.session_state.xlsx_first_bar_offset,
            time_signature=time_sig if 'time_sig' in locals() else "4/4",
            split_unit=split_unit if 'split_unit' in locals() else "4小節ごと",
            visual_style=vis_style if 'vis_style' in locals() else "特になし",
            aspect_ratio=aspect_ratio if 'aspect_ratio' in locals() else "16:9"
        )
        
        st.download_button(
            label="📥 スタイリングされた Excel (.xlsx) をダウンロード",
            data=xlsx_bytes,
            file_name=f"{project_title}_timeline.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        st.info("💡 ダウンロードした Excel ファイルは、既存の「自走型MVジェネレーター (`app.py`)」のサイドバーからそのまま読み込むことができます。")
    except Exception as e_xlsx:
        st.error(f"Excelファイル生成エラー: {e_xlsx}")
