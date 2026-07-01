import streamlit as st
import os
import json
import tempfile
import pandas as pd
import shutil
from utils import save_project, load_project, analyze_audio, generate_initial_timeline, parse_tagged_lyrics, refine_image_prompt, export_project_zip, import_project_zip
from video_utils import generate_imagen_image, build_slideshow

st.set_page_config(page_title="自走型MVジェネレーター - タイムライン作成", layout="wide")

# タイトル
st.title("🎬 自走型MVジェネレーター - フェーズ1: タイムライン作成")

# セッション状態の初期化
if "timeline_data" not in st.session_state:
    st.session_state.timeline_data = None
if "bpm" not in st.session_state:
    st.session_state.bpm = 120.0
if "duration" not in st.session_state:
    st.session_state.duration = 180.0
if "project_name" not in st.session_state:
    st.session_state.project_name = "my_mv_project"
if "core_concept" not in st.session_state:
    st.session_state.core_concept = ""
if "global_rules" not in st.session_state:
    st.session_state.global_rules = ""
if "section_rules" not in st.session_state:
    st.session_state.section_rules = ""
if "keywords" not in st.session_state:
    st.session_state.keywords = ""
if "lyrics" not in st.session_state:
    st.session_state.lyrics = ""
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None

# サイドバー設定
st.sidebar.header("🛠️ 設定")

# APIキーの入力
api_key_input = st.sidebar.text_input("Gemini API Key", type="password", 
                                     value=os.environ.get("GEMINI_API_KEY", ""),
                                     help="APIキーを入力するか、プロジェクトの.envファイルにGEMINI_API_KEYを設定してください。")
st.sidebar.link_button("🔑 APIキーを取得 (Google AI Studio)", "https://aistudio.google.com/app/apikey")

# プロジェクトの保存・読込UI
st.sidebar.subheader("💾 プロジェクトの管理")
project_file = st.sidebar.file_uploader("プロジェクトファイルを読み込み (.json / .xlsx / .zip)", type=["json", "xlsx", "zip"])

if project_file is not None:
    try:
        if project_file.name.endswith(".json"):
            data = json.load(project_file)
            st.session_state.timeline_data = data.get("timeline", [])
            st.session_state.bpm = data.get("bpm", 120.0)
            st.session_state.duration = data.get("duration", 180.0)
            st.session_state.project_name = data.get("project_name", "loaded_project")
            
            # タイムラインから歌詞を再構築して復元
            reconstructed_lyrics = []
            last_section = None
            for item in st.session_state.timeline_data:
                sec = item.get("section", "")
                lyr = item.get("lyrics", "")
                if sec and sec != last_section:
                    reconstructed_lyrics.append(f"\n[{sec}]")
                    last_section = sec
                if lyr:
                    reconstructed_lyrics.append(lyr)
            st.session_state.lyrics = "\n".join(reconstructed_lyrics).strip()
        elif project_file.name.endswith(".xlsx"):
            # Excelファイルの読込
            # Sheet 1: 概要
            df_summary = pd.read_excel(project_file, sheet_name=0)
            summary_dict = dict(zip(df_summary["項目"], df_summary["内容"]))
            
            # 各項目を復元
            st.session_state.project_name = str(summary_dict.get("提案タイトル", "loaded_project"))
            st.session_state.bpm = float(summary_dict.get("BPM", 120.0))
            st.session_state.duration = float(summary_dict.get("曲の長さ (秒)", 180.0))
            
            # 世界観などのテキストもセッションに復元
            st.session_state.core_concept = str(summary_dict.get("世界観・コンセプト", ""))
            st.session_state.global_rules = str(summary_dict.get("全体演出ルール", ""))
            
            # Sheet 2: タイムライン
            df_timeline = pd.read_excel(project_file, sheet_name=1)
            # NaNを空文字に置換
            df_timeline = df_timeline.fillna("")
            st.session_state.timeline_data = df_timeline.to_dict(orient="records")
            
            # タイムラインから歌詞を再構築して復元
            reconstructed_lyrics = []
            last_section = None
            for item in st.session_state.timeline_data:
                sec = item.get("section", "")
                lyr = item.get("lyrics", "")
                if sec and sec != last_section:
                    reconstructed_lyrics.append(f"\n[{sec}]")
                    last_section = sec
                if lyr:
                    reconstructed_lyrics.append(lyr)
            st.session_state.lyrics = "\n".join(reconstructed_lyrics).strip()
        elif project_file.name.endswith(".zip"):
            # ZIPパッケージファイルのロード
            images_dir = "assets/images"
            extract_dir = tempfile.mkdtemp()
            try:
                project_data = import_project_zip(
                    zip_file=project_file,
                    extract_dir=extract_dir,
                    images_target_dir=images_dir
                )
                st.session_state.project_name = project_data["project_name"]
                st.session_state.bpm = project_data["bpm"]
                st.session_state.duration = project_data["duration"]
                st.session_state.timeline_data = project_data["timeline"]
                st.session_state.audio_path = project_data["audio_path"]
                
                # タイムラインから歌詞を再構築して復元
                reconstructed_lyrics = []
                last_section = None
                for item in st.session_state.timeline_data:
                    sec = item.get("section", "")
                    lyr = item.get("lyrics", "")
                    if sec and sec != last_section:
                        reconstructed_lyrics.append(f"\n[{sec}]")
                        last_section = sec
                    if lyr:
                        reconstructed_lyrics.append(lyr)
                st.session_state.lyrics = "\n".join(reconstructed_lyrics).strip()
            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)
            
        st.sidebar.success("プロジェクトを読み込みました！")
    except Exception as e:
        st.sidebar.error(f"読み込み失敗: {e}")

# 保存用のダウンロードボタン
if st.session_state.timeline_data:
    col_save_json, col_save_zip = st.sidebar.columns(2)
    
    with col_save_json:
        export_data = {
            "project_name": st.session_state.project_name,
            "bpm": st.session_state.bpm,
            "duration": st.session_state.duration,
            "timeline": st.session_state.timeline_data
        }
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 JSON保存",
            data=json_str,
            file_name=f"{st.session_state.project_name}.json",
            mime="application/json"
        )
        
    with col_save_zip:
        try:
            zip_bytes = export_project_zip(
                project_name=st.session_state.project_name,
                timeline_data=st.session_state.timeline_data,
                bpm=st.session_state.bpm,
                duration=st.session_state.duration,
                audio_path=st.session_state.get("audio_path"),
                images_dir="assets/images"
            )
            st.download_button(
                label="📥 ZIP保存",
                data=zip_bytes,
                file_name=f"{st.session_state.project_name}_package.zip",
                mime="application/zip"
            )
        except Exception as e_zip_export:
            st.sidebar.error(f"ZIP書き出し失敗: {e_zip_export}")

# メインコンテンツ
tab1, tab2, tab3 = st.tabs(["📝 新規作成・解析", "📊 タイムライン編集", "🎨 デモ動画・画像生成"])

with tab1:
    st.header("1. プロジェクト設定と素材入力")
    
    col1, col2 = st.columns(2)
    
    with col1:
        project_name = st.text_input("プロジェクト名", value=st.session_state.project_name)
        st.session_state.project_name = project_name
        
        st.markdown("### 📝 歌詞入力")
        st.info("💡 各行の先頭に `[Intro]` や `[サビ]`、`[A-Melody]` のようにタグを書くことで、AIにセクション構成を明示できます。")
        lyrics = st.text_area(
            "歌詞 (セクションタグ付き)", 
            value=st.session_state.lyrics,
            height=200, 
            placeholder="例:\n[Intro]\n(インスト演奏)\n\n[A-Melody]\n夜の街を駆け抜ける君の影...\n\n[Chorus]\nサビの歌詞がここに入ります...",
            help="[セクション名] で区切ることで、AIが正確に構成を認識します。"
        )
        
        # 歌詞の構造プレビューを表示
        if lyrics:
            parsed_lyrics = parse_tagged_lyrics(lyrics)
            if parsed_lyrics:
                with st.expander("🔍 認識されたセクション構成（プレビュー）", expanded=True):
                    for item in parsed_lyrics:
                        sec = item['section']
                        lyr = item['lyrics'].strip().replace('\n', ' / ')
                        preview_txt = lyr[:40] + "..." if len(lyr) > 40 else lyr
                        st.write(f"**🔷 {sec}**: *{preview_txt}*")
        
        st.markdown("### 🎬 映像の演出・プロット設定 (重要度別)")
        core_concept = st.text_area(
            "🌟 【最優先】世界観・キャラクター設定", 
            value=st.session_state.core_concept,
            height=100, 
            placeholder="例: 主人公は無表情な黒髪 of 少女。退廃的なサイバーパンク都市の路地裏。青いネオンカラーが基調..."
        )
        global_rules = st.text_area(
            "📋 【優先】全体演出ルール / 盛り上がり制御", 
            value=st.session_state.global_rules,
            height=80, 
            placeholder="例: 全体的にカメラはローアングル。サビ(Chorus)ではネオンが激しく点滅し、映像の切り替え（カット割）を細かくする..."
        )
        section_rules = st.text_area(
            "🎵 【推奨】セクションごとの個別ルール", 
            value=st.session_state.section_rules,
            height=80, 
            placeholder="例: Introはモノクロ調で静かに開始。Outroは朝焼けの中へ消えていくカット..."
        )
        keywords = st.text_input(
            "🔑 【任意】取り入れたい象徴的なキーワード (カンマ区切り)", 
            value=st.session_state.keywords,
            placeholder="例: 雨, 青い蝶, 割れた鏡, 時計の歯車"
        )

    with col2:
        st.subheader("🎵 音源ファイルとテンポ")
        audio_file = st.file_uploader("音源ファイルをアップロード (BPMと長さを自動解析します)", type=["mp3", "wav", "m4a", "ogg"])
        
        if audio_file is not None:
            # 音源ファイルをローカルのassetsに永続保存
            os.makedirs("assets", exist_ok=True)
            saved_audio_path = os.path.join("assets", f"audio_{audio_file.name}")
            if "audio_path" not in st.session_state or st.session_state.audio_path != saved_audio_path:
                with open(saved_audio_path, "wb") as f:
                    f.write(audio_file.getbuffer())
                st.session_state.audio_path = saved_audio_path
                
            if st.button("🎵 音源を解析する"):
                with st.spinner("音源を解析中... (LibrosaによるBPMおよび曲長検出)"):
                    # 一時ファイルに保存して解析
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.name)[1]) as temp_file:
                        temp_file.write(audio_file.read())
                        temp_path = temp_file.name
                    
                    analysis = analyze_audio(temp_path)
                    os.unlink(temp_path) # 一時ファイルの削除
                    
                    if analysis:
                        st.session_state.bpm = analysis["bpm"]
                        st.session_state.duration = analysis["duration"]
                        st.success(f"解析完了！ BPM: {analysis['bpm']} | 曲長: {analysis['duration']}秒")
                    else:
                        st.error("音源の解析に失敗しました。")
        
        manual_bpm = st.number_input("テンポ (BPM) 手動調整", min_value=1.0, max_value=300.0, value=st.session_state.bpm, step=0.1)
        if st.session_state.bpm != manual_bpm:
            st.session_state.bpm = manual_bpm
        
        manual_duration = st.number_input("曲の長さ (秒) 手動調整", min_value=1.0, max_value=600.0, value=st.session_state.duration, step=1.0)
        if st.session_state.duration != manual_duration:
            st.session_state.duration = manual_duration
        
    st.markdown("---")
    
    if st.button("🚀 AIによる初期カット割り生成"):
        if not api_key_input and not os.environ.get("GEMINI_API_KEY"):
            st.error("Gemini API Keyを設定してください（サイドバーに入力、または.envファイルに記述）。")
        elif not lyrics:
            st.warning("歌詞を入力してください。")
        elif not core_concept:
            st.warning("【最優先】世界観・キャラクター設定を入力してください。")
        else:
            with st.spinner("Gemini APIがカット割りを設計中..."):
                try:
                    result = generate_initial_timeline(
                        lyrics=lyrics,
                        bpm=st.session_state.bpm,
                        duration=st.session_state.duration,
                        core_concept=core_concept,
                        global_rules=global_rules,
                        section_rules=section_rules,
                        keywords=keywords,
                        api_key=api_key_input
                    )
                    if result and "timeline" in result:
                        st.session_state.timeline_data = result["timeline"]
                        st.success("初期タイムラインの作成に成功しました！『タイムライン編集』タブで確認・手直しを行ってください。")
                    else:
                        st.error("AIからのデータ生成に失敗しました。応答フォーマットを確認してください。")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

with tab2:
    st.header("2. タイムラインの確認と編集")
    
    if st.session_state.timeline_data is None or len(st.session_state.timeline_data) == 0:
        st.info("新規作成タブで初期タイムラインを作成するか、保存したJSONプロジェクトファイルを読み込んでください。")
    else:
        st.subheader("📋 カット割り一覧 (ダブルクリックで直接編集できます)")
        
        # DataFrame化してStreamlitのdata_editorで編集可能にする
        df = pd.DataFrame(st.session_state.timeline_data)
        
        # 列の表示順などを整理
        cols = ["section", "start_time", "end_time", "lyrics", "description", "prompt"]
        df = df[cols]
        
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "section": st.column_config.TextColumn("セクション (Aメロ/サビ等)", width="medium"),
                "start_time": st.column_config.NumberColumn("開始秒数 (s)", min_value=0.0, format="%.2f"),
                "end_time": st.column_config.NumberColumn("終了秒数 (s)", min_value=0.0, format="%.2f"),
                "lyrics": st.column_config.TextColumn("歌詞", width="large"),
                "description": st.column_config.TextColumn("映像の日本語説明", width="large"),
                "prompt": st.column_config.TextColumn("画像生成プロンプト(英)", width="large"),
            }
        )
        
        # 編集結果をセッションに書き戻す (無限ループ防止のため、値が変更された場合のみ更新)
        new_timeline_data = edited_df.to_dict(orient="records")
        if st.session_state.timeline_data != new_timeline_data:
            st.session_state.timeline_data = new_timeline_data
            st.rerun()
        
        st.subheader("🔍 現在の絵コンテ確認用プレビュー")
        for i, cut in enumerate(st.session_state.timeline_data):
            with st.expander(f"Cut {i+1} [{cut.get('section', 'N/A')}] {cut.get('start_time', 0.0)}s - {cut.get('end_time', 0.0)}s"):
                st.markdown(f"**歌詞:** {cut.get('lyrics', '(なし)')}")
                st.markdown(f"**映像演出:** {cut.get('description', '')}")
                st.markdown(f"**画像生成プロンプト (AI用):** `{cut.get('prompt', '')}`")

with tab3:
    st.header("3. カット画像生成 & スライドショーデモ動画化")
    
    if st.session_state.timeline_data is None or len(st.session_state.timeline_data) == 0:
        st.info("新規作成タブでタイムラインを作成するか、プロジェクトファイルを読み込んでください。")
    else:
        # パス設定
        images_dir = "assets/images"
        output_video_path = "assets/demo_mv.mp4"
        os.makedirs(images_dir, exist_ok=True)
        
        col_ctrl, col_view = st.columns([1, 2])
        
        with col_ctrl:
            st.subheader("🎬 デモVコンテ（仮MV）の生成")
            st.write("画像を生成していないカットは、自動的に仮画像（歌詞・構成テキスト入り）が挿入されます。")
            
            if "audio_path" in st.session_state and st.session_state.audio_path:
                st.info(f"使用中音源: {os.path.basename(st.session_state.audio_path)}")
            else:
                st.warning("⚠️ 音源がアップロードされていません。スライドショー動画を音楽とマージするために、新規作成タブで音源をアップロードしてください。")
                
            if st.button("🎥 スライドショー動画 (MP4) をレンダリング"):
                with st.spinner("動画を結合・出力中... (これには数十秒かかる場合があります)"):
                    audio_p = st.session_state.get("audio_path", None)
                    success = build_slideshow(
                        timeline=st.session_state.timeline_data,
                        audio_path=audio_p,
                        output_path=output_video_path,
                        images_dir=images_dir
                    )
                    if success:
                        st.success("動画の書き出しに成功しました！右側のプレイヤーで再生できます。")
                    else:
                        st.error("動画の書き出しに失敗しました。")
            
            st.markdown("---")
            st.subheader("🎯 カット選択 (個別画像生成)")
            
            # ドロップダウンでカットを選択
            cut_options = [
                f"Cut {i+1} [{cut.get('section', 'N/A')}] {cut.get('start_time')}s - {cut.get('end_time')}s"
                for i, cut in enumerate(st.session_state.timeline_data)
            ]
            selected_cut_index = st.selectbox("生成・編集するカットを選択", range(len(cut_options)), format_func=lambda x: cut_options[x])
            
            current_cut = st.session_state.timeline_data[selected_cut_index]
            
            st.markdown(f"**現在の歌詞**: {current_cut.get('lyrics', '(なし)')}")
            st.markdown(f"**演出説明**: {current_cut.get('description', '')}")
            
            # 英語プロンプト入力エリア
            prompt_key = f"prompt_input_{selected_cut_index}"
            if prompt_key not in st.session_state:
                st.session_state[prompt_key] = current_cut.get("prompt", "")
                
            edited_prompt = st.text_area(
                "画像生成プロンプト (英語)", 
                value=st.session_state[prompt_key],
                key=f"area_{prompt_key}",
                height=120
            )
            # 値を更新
            st.session_state[prompt_key] = edited_prompt
            st.session_state.timeline_data[selected_cut_index]["prompt"] = edited_prompt
            
            # 対話的なプロンプト改善
            st.markdown("##### ✨ プロンプトの対話的リファイン")
            feedback = st.text_input("日本語での追加指示・修正（例: 夜にして、雨を追加など）", key=f"feed_{selected_cut_index}")
            
            if st.button("🌟 プロンプトをAIで改善", key=f"btn_ref_{selected_cut_index}"):
                if not feedback:
                    st.warning("指示を入力してください。")
                elif not api_key_input and not os.environ.get("GEMINI_API_KEY"):
                    st.error("Gemini API Keyを設定してください。")
                else:
                    with st.spinner("プロンプトをブラッシュアップ中..."):
                        refined = refine_image_prompt(
                            current_prompt=edited_prompt,
                            user_feedback=feedback,
                            api_key=api_key_input
                        )
                        st.session_state[prompt_key] = refined
                        st.session_state.timeline_data[selected_cut_index]["prompt"] = refined
                        st.rerun() # リロードして反映
                        
            # 個別画像生成ボタン (ローカルGPU優先)
            if st.button("🎨 このカットの画像を生成 (ローカルGPU優先)", key=f"btn_gen_{selected_cut_index}"):
                with st.status("画像を生成中...", expanded=True) as status:
                    log_placeholder = st.empty()
                    logs = []
                    
                    def update_log(line):
                        logs.append(line)
                        log_placeholder.code("\n".join(logs[-10:])) # 直近10行を表示
                    
                    img_path = os.path.join(images_dir, f"cut_{selected_cut_index}.png")
                    success, status_msg = generate_imagen_image(
                        prompt=st.session_state[prompt_key],
                        output_path=img_path,
                        api_key=api_key_input,
                        log_callback=update_log
                    )
                    
                    if success:
                        status.update(label="画像生成完了！", state="complete", expanded=False)
                        if status_msg == "LOCAL_SUCCESS":
                            st.success("🎉 画像生成に成功しました！（ローカルGPU: DreamShaper-8 を使用）")
                        elif status_msg == "CLOUD_SUCCESS":
                            st.success("🎉 画像生成に成功しました！（クラウドAPI: Imagen を使用）")
                        else:
                            st.success(f"🎉 画像生成に成功しました！ ({status_msg})")
                        st.rerun()
                    else:
                        status.update(label="画像生成に失敗しました", state="error", expanded=True)
                        if status_msg == "PAID_PLAN_REQUIRED":
                            st.error("❌ 画像生成エラー: 現在のAPIキー（無料プラン）では画像生成（Imagen 3）をご利用いただけません。画像生成機能を使うには、Google AI Studioコンソールで有料プラン（従量課金設定）にアップグレードしてカード情報を登録する必要があります。")
                            st.info("💡 解決策: ①ローカルGPU（RTX 3060/4060等）が正しく認識されれば自動的に無料ローカル生成が動きます。 ②画像生成を行わない状態でも、左側の『スライドショー動画をレンダリング』ボタンを押すことで、歌詞付きの仮画面によるデモ動画を作成可能です！")
                        else:
                            st.error(f"画像生成に失敗しました: {status_msg}")

        with col_view:
            st.subheader("📺 プレビュー")
            
            # ビデオプレイヤーの設置
            if os.path.exists(output_video_path):
                st.video(output_video_path)
            else:
                st.info("デモVコンテ（動画）は未生成です。左側の「スライドショー動画をレンダリング」ボタンを押すと生成されます。")
                
            st.markdown("---")
            st.subheader("🖼️ 選択中のカット画像プレビュー")
            
            target_img_path = os.path.join(images_dir, f"cut_{selected_cut_index}.png")
            if os.path.exists(target_img_path):
                st.image(target_img_path, caption=f"Cut {selected_cut_index+1} の生成画像", use_container_width=True)
            else:
                st.warning("⚠️ このカットの画像はまだ生成されていません。スライドショー生成時は自動で仮画像（歌詞表示）が作成されます。")
