import os
import json
import librosa
import google.generativeai as genai
from dotenv import load_dotenv
import re
import io
import pandas as pd
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import mido

load_dotenv()

def parse_tagged_lyrics(raw_lyrics):
    """
    [Intro], [サビ], [A-Melody] などのタグで区切られた歌詞をパースして
    セクションごとのリストを作成する
    """
    if not raw_lyrics:
        return []
        
    pattern = r'\[([^\]]+)\]'
    segments = re.split(pattern, raw_lyrics)
    
    parsed = []
    
    # 最初がタグから始まらない場合のテキスト
    first_text = segments[0].strip()
    if first_text:
        parsed.append({"section": "Intro", "lyrics": first_text})
        
    for i in range(1, len(segments), 2):
        section_name = segments[i].strip()
        lyrics_text = segments[i+1].strip() if i+1 < len(segments) else ""
        if lyrics_text or section_name:
            parsed.append({"section": section_name, "lyrics": lyrics_text})
            
    return parsed

def get_lyrics_lines_with_sections(raw_lyrics):
    """
    歌詞をセクションごとにパースし、空行を除外した『行単位』のリストにする
    例: [{"section": "Verse 1", "line": "届かない"}, {"section": "Verse 1", "line": "響かない"}]
    """
    sections = parse_tagged_lyrics(raw_lyrics)
    line_list = []
    
    for sec in sections:
        sec_name = sec["section"]
        lyrics_text = sec["lyrics"]
        lines = [l.strip() for l in lyrics_text.split("\n") if l.strip()]
        
        # 歌詞が空の場合はダミー行を1つ置く
        if not lines:
            line_list.append({"section": sec_name, "line": ""})
        else:
            for l in lines:
                line_list.append({"section": sec_name, "line": l})
                
    return line_list

def align_lyrics_with_midi(midi_path, raw_lyrics, duration):
    """
    MIDIファイルのメロディ音符（Note On）から発音区間（フレーズ）を抽出し、
    入力された歌詞（行単位）とミリ秒単位で完全に同期させた初期タイムライン枠を作成する。
    """
    try:
        mid = mido.MidiFile(midi_path)
    except Exception as e:
        print(f"Error loading MIDI file: {e}")
        return None

    # 1. MIDI全イベントを絶対秒数に解決してノートオンを抽出
    notes = [] 
    active_notes = {}
    current_time = 0.0
    markers = [] 
    
    for msg in mid:
        current_time += msg.time
        if msg.type == 'marker':
            markers.append((current_time, msg.text.strip()))
        elif msg.type == 'note_on' and msg.velocity > 0:
            active_notes[msg.note] = current_time
        elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active_notes:
                start_time = active_notes.pop(msg.note)
                end_time = current_time
                if end_time - start_time > 0.05:
                    notes.append((start_time, end_time, msg.note))

    notes.sort(key=lambda x: x[0])
    
    # 2. 発音タイミングを「休符（無音区間）」で区切る (1.5秒以上の休符)
    phrase_groups = []
    if notes:
        current_group = [notes[0]]
        for note in notes[1:]:
            last_note = current_group[-1]
            rest_duration = note[0] - last_note[1]
            if rest_duration > 1.5:
                phrase_groups.append(current_group)
                current_group = [note]
            else:
                current_group.append(note)
        phrase_groups.append(current_group)

    # 各グループの開始・終了時間（秒）を計算
    midi_phrases = []
    for gp in phrase_groups:
        start_time = gp[0][0]
        end_time = gp[-1][1]
        start_time = max(0.0, start_time - 0.2)
        end_time = min(duration, end_time + 0.2)
        midi_phrases.append({"start_time": round(start_time, 3), "end_time": round(end_time, 3)})

    # 3. 歌詞テキストをセクション・行単位に分解
    lyrics_lines = get_lyrics_lines_with_sections(raw_lyrics)

    # 4. MIDIのフレーズ枠と歌詞行を時系列でマッピング (アライメント)
    timeline_slots = []
    
    # 前奏区間の追加 (最初の音符が始まるまで)
    first_singing_time = midi_phrases[0]["start_time"] if midi_phrases else 0.0
    if first_singing_time > 1.0:
        intro_label = "Intro"
        if markers:
            if markers[0][0] < first_singing_time:
                intro_label = markers[0][1]
        timeline_slots.append({
            "section": intro_label,
            "start_time": 0.0,
            "end_time": first_singing_time,
            "lyrics": ""
        })

    # フレーズごとの割り当て
    num_midi_phrases = len(midi_phrases)
    num_lyrics_lines = len(lyrics_lines)
    
    if num_lyrics_lines == 0:
        for i, phrase in enumerate(midi_phrases):
            timeline_slots.append({
                "section": f"Instrumental {i+1}",
                "start_time": phrase["start_time"],
                "end_time": phrase["end_time"],
                "lyrics": ""
            })
    else:
        for idx in range(max(num_midi_phrases, num_lyrics_lines)):
            if idx < num_midi_phrases and idx < num_lyrics_lines:
                phrase = midi_phrases[idx]
                lyr_info = lyrics_lines[idx]
                timeline_slots.append({
                    "section": lyr_info["section"],
                    "start_time": phrase["start_time"],
                    "end_time": phrase["end_time"],
                    "lyrics": lyr_info["line"]
                })
            elif idx < num_midi_phrases:
                phrase = midi_phrases[idx]
                timeline_slots.append({
                    "section": "Instrumental/Solo",
                    "start_time": phrase["start_time"],
                    "end_time": phrase["end_time"],
                    "lyrics": ""
                })
            elif idx < num_lyrics_lines:
                last_end = timeline_slots[-1]["end_time"] if timeline_slots else 0.0
                lyr_info = lyrics_lines[idx]
                start = round(last_end, 3)
                end = round(min(duration, start + 4.0), 3)
                if start < duration:
                    timeline_slots.append({
                        "section": lyr_info["section"],
                        "start_time": start,
                        "end_time": end,
                        "lyrics": lyr_info["line"]
                    })

    # カット間の「隙間」を埋める
    seamless_slots = []
    for i in range(len(timeline_slots)):
        current_slot = timeline_slots[i]
        
        if i == 0 and current_slot["start_time"] > 0.0:
            seamless_slots.append({
                "section": "Intro",
                "start_time": 0.0,
                "end_time": current_slot["start_time"],
                "lyrics": ""
            })
            
        seamless_slots.append(current_slot)
        
        if i < len(timeline_slots) - 1:
            next_slot = timeline_slots[i+1]
            gap = next_slot["start_time"] - current_slot["end_time"]
            if gap > 0.5:
                seamless_slots.append({
                    "section": "Interlude",
                    "start_time": current_slot["end_time"],
                    "end_time": next_slot["start_time"],
                    "lyrics": ""
                })
            elif gap > 0.0:
                current_slot["end_time"] = next_slot["start_time"]

    if seamless_slots and seamless_slots[-1]["end_time"] < duration:
        last_slot = seamless_slots[-1]
        if last_slot["lyrics"] == "":
            last_slot["end_time"] = duration
        else:
            seamless_slots.append({
                "section": "Outro",
                "start_time": last_slot["end_time"],
                "end_time": duration,
                "lyrics": ""
            })

    valid_slots = []
    for slot in seamless_slots:
        if slot["end_time"] > slot["start_time"]:
            valid_slots.append(slot)
            
    return valid_slots

def analyze_audio(audio_path):
    """音声ファイルを解析してBPMと曲の長さを返す"""
    try:
        y, sr = librosa.load(audio_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        
        if isinstance(tempo, (list, tuple, bytes, dict)) or hasattr(tempo, '__iter__'):
            bpm = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            bpm = float(tempo)
            
        return {
            "bpm": round(bpm, 2),
            "duration": round(duration, 2)
        }
    except Exception as e:
        print(f"Error analyzing audio: {e}")
        return None

# =====================================================================
# 【ステップ1: 設定制作フェーズ】
# =====================================================================
def generate_concept_settings(lyrics, bpm, duration, raw_idea="", api_key=None, audio_path=None):
    """
    楽曲の歌詞、BPM、長さ、およびユーザーのラフ要望から、
    AIが「世界観・コンセプト」「キャラクター設定」「色彩・演出ルール」の全体設定を設計・提案する
    """
    if api_key:
        genai.configure(api_key=api_key)
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    else:
        raise ValueError("Gemini API key is not configured.")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
あなたはプロのミュージックビデオ(MV)監督およびビジュアルデザイナーです。
入力された楽曲データとユーザーのラフアイデアから、MV全体の根底となる「世界観」「キャラクターデザイン」「共通色彩設計」を高度に設計・提案してください。

【入力データ】
- 歌詞:
\"\"\"
{lyrics}
\"\"\"
- テンポ (BPM): {bpm}
- 全体の長さ: {duration}秒
- ユーザーのビジュアル要望・ラフイメージ: "{raw_idea if raw_idea else "特になし (歌詞と雰囲気から自動提案)"}"

【設計の条件】
1. この設定は、後続の「各カットの画像生成プロンプト」に共通で強制適用される「マスター設定図」となります。
2. そのため、以下の各項目は具体的かつ、後の画像生成AI (Imagen 3 等) が解釈して一貫性を保てるように視覚的（Visual）に記述してください。
   - 提案タイトル: 楽曲のコンセプトを表現するビジュアルタイトル。
   - 世界観・コンセプト設定: 背景の建築様式、ライティング、空気感、季節、時間帯など。
   - キャラクター詳細設定: 主人公等の性別、推定年齢、髪型・髪色、目の色、服装（色や素材も詳細に）、表情の傾向など。
   - 色彩設計と演出ルール: カラーパレット（色彩の統一感、基調とする色）、映像のカメラワーク・質感（シネマティック、手持ちカメラ、アニメ風など）。

必ず以下のJSONスキーマに従って結果を返してください。JSON以外の文章は一切出力しないでください。

【出力フォーマット (JSON)】
{{
  "title": "提案するプロジェクトタイトル（日本語または英語）",
  "concept": "自動設計した世界観・コンセプト設定（背景やライティングなどの視覚的詳細、日本語、200〜300文字程度）",
  "characters": "自動設計したキャラクターデザイン（髪型、服装、色などの視覚的詳細、日本語、200〜300文字程度）",
  "rules": "自動設計した全体の色彩パレット ＆ 共通演出トーン（基調色やカメラワークの質感、日本語、150〜200文字程度）"
}}
"""

    contents = []
    audio_file_ref = None
    
    if audio_path and os.path.exists(audio_path):
        print(f"[INFO] Concept phase: Uploading audio file to Gemini API: {audio_path}")
        try:
            audio_file_ref = genai.upload_file(path=audio_path)
            contents.append(audio_file_ref)
            print("[INFO] Audio upload completed.")
        except Exception as e:
            print(f"[WARNING] Failed to upload audio: {e}")

    contents.append(prompt)

    try:
        response = model.generate_content(
            contents,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.4
            }
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Failed to parse Gemini response as JSON in Concept Phase: {e}")
        return None
    finally:
        if audio_file_ref:
            try:
                genai.delete_file(audio_file_ref.name)
            except:
                pass


def generate_test_image_prompt(concept_summary, visual_style="特になし", aspect_ratio="16:9", api_key=None):
    """
    確定したコンセプト、キャラクター設定、色彩設計、および指定されたスタイルから、
    世界観を代表する「テスト画像用の英語プロンプト」を1枚分自動合成する。
    """
    if api_key:
        genai.configure(api_key=api_key)
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    else:
        raise ValueError("Gemini API key is not configured.")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    title = concept_summary.get("title", "Song Project")
    concept_desc = concept_summary.get("concept", "")
    character_desc = concept_summary.get("characters", "")
    rules_desc = concept_summary.get("rules", "")

    prompt = f"""
あなたは画像生成AI(Imagen 3 / Stable Diffusion)用の卓越したプロンプトデザイナーです。
入力された【ミュージックビデオ(MV)の世界観設定・キャラクターデザイン・色彩トーン】を元に、
そのビジュアルを象徴する、最も代表的で高品質な「1枚のテスト画像生成用の英語プロンプト」を構築してください。

【MVのビジュアル設定】
- 世界観コンセプト: 
\"\"\"
{concept_desc}
\"\"\"
- キャラクター設定: 
\"\"\"
{character_desc}
\"\"\"
- 色彩設計と演出トーン: 
\"\"\"
{rules_desc}
\"\"\"
- 指定ビジュアルスタイル: {visual_style}
- アスペクト比: {aspect_ratio}

【構築条件】
1. キャラクター設定に記載された外見的特徴（髪型、目の色、服装など）を詳細に反映してください。
2. 世界観コンセプトに書かれた背景、ライティング（光の当たり方）、カラーパレットの色彩設計ルールを自然に含めてください。
3. 指定スタイル（{visual_style}）を表現するのに最適なカメラワークや質感のキーワードを盛り込み、高精細かつアーティスティックな英語のプロンプト（約100〜150ワード程度）に仕上げてください。
4. 出力は、生成された「英語の画像プロンプトのみ」を返してください。それ以外の挨拶文や説明、マークダウンのコードブロックは一切含めないでください。
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('`', '')
    except Exception as e:
        print(f"Failed to generate test image prompt: {e}")
        return None

# =====================================================================
# 【ステップ2: コンテ制作フェーズ (トップダウン流し込み)】
# =====================================================================
def generate_timeline_from_concept(lyrics, bpm, duration, concept_summary, api_key=None,
                                   first_bar_offset=0.0, time_signature="4/4",
                                   visual_style="特になし", aspect_ratio="16:9",
                                   audio_path=None, midi_path=None):
    """
    確定したコンセプト設定図をベースにして、MIDI（あれば）と歌詞から
    世界観が完全に統一されたカットタイムライン（プロンプト付き）を自動構築する
    """
    if api_key:
        genai.configure(api_key=api_key)
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    else:
        raise ValueError("Gemini API key is not configured.")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 1. MIDIによるローカル精密アライメント
    timeline_slots = None
    if midi_path and os.path.exists(midi_path):
        print(f"[INFO] MIDI alignment mode: {midi_path}")
        timeline_slots = align_lyrics_with_midi(midi_path, lyrics, duration)
        
    if timeline_slots is None:
        print("[INFO] Text-based fallback mode.")
        structured_lyrics = parse_tagged_lyrics(lyrics)
        lyrics_json_str = json.dumps(structured_lyrics, indent=2, ensure_ascii=False)
    else:
        lyrics_json_str = json.dumps(timeline_slots, indent=2, ensure_ascii=False)
        
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * 4 # 4/4前提の標準1小節
    
    # コンセプトテキストのパース
    title = concept_summary.get("title", "Song Project")
    concept_desc = concept_summary.get("concept", "")
    character_desc = concept_summary.get("characters", "")
    rules_desc = concept_summary.get("rules", "")

    # プロンプトの組み立て (トップダウン指示)
    prompt = f"""
あなたはプロのミュージックビデオ(MV)監督および映像プランナーです。
ステップ1で決定した【MVのマスタービジュアル設定】を「絶対の前提」として固定し、各カットのタイムライン（コンテ）を作成してください。

【MVのマスタービジュアル設定 (世界観の統一規格)】
- タイトル: "{title}"
- 世界観コンセプト: 
\"\"\"
{concept_desc}
\"\"\"
- キャラクタービジュアル設定: 
\"\"\"
{character_desc}
\"\"\"
- 色彩設計と演出共通ルール: 
\"\"\"
{rules_desc}
\"\"\"

【入力データ】
- タイムライン枠組み (start_time と end_time、および歌詞):
```json
{lyrics_json_str}
```
- テンポ (BPM): {bpm}
- 全体の長さ: {duration}秒
- 1小節目の開始時間 (オフセット秒): {first_bar_offset}秒
- アスペクト比: {aspect_ratio}
- 指定ビジュアルスタイル: {visual_style}

【設計・展開の条件 (世界観の統一化)】
1. 渡されたJSONの各スロットの `start_time`、`end_time`、`section`、`lyrics` は一切変更しないでください。
2. 【プロンプトへのトップダウン流し込み】
   - 各カットに設定する画像生成プロンプト（`prompt`：英語）には、上記の『キャラクタービジュアル設定（髪型、目の色、服装など）』および『世界観コンセプト（背景、ライティング）』、『色彩設計』の要素を、**すべてのプロンプトに必ず漏れなく埋め込んでください。**
   - カット間でキャラクターの見た目（服装や髪）や、背景のビジュアルトーン、カラーパレットが絶対にブレないようにしてください。
3. 各カットの歌詞とタイミングに完璧にフィットする、魅力的な【映像演出説明 (description)】（日本語）と、画像生成AI用の具体的かつ高品質な【画像生成プロンプト (prompt)】（英語）をあなたが考えて、JSONの空欄部分を埋めてください。
4. 指定されたスタイル「{visual_style}」およびアスペクト比「{aspect_ratio}」をプロンプト内に自然に、かつ強力に反映させてください。

必ず以下のJSONスキーマに従って結果を返してください。JSON以外の文章は一切出力しないでください。

【出力フォーマット (JSON)】
{{
  "bpm": {bpm},
  "duration": {duration},
  "summary": {{
    "title": "{title}",
    "concept": "{concept_desc}",
    "characters": "{character_desc}",
    "rules": "{rules_desc}"
  }},
  "timeline": [
    {{
      "section": "セクション名",
      "start_time": 0.0,
      "end_time": 10.0,
      "lyrics": "歌詞の一節",
      "description": "演出・カメラワークの詳細な日本語説明（色彩設計や共通演出を反映）",
      "prompt": "Highly detailed image generation prompt in English, including character details and color rules for consistency"
    }}
  ]
}}
"""

    contents = []
    audio_file_ref = None
    
    if audio_path and os.path.exists(audio_path):
        print(f"[INFO] Timeline phase: Uploading audio file to Gemini API: {audio_path}")
        try:
            audio_file_ref = genai.upload_file(path=audio_path)
            contents.append(audio_file_ref)
        except Exception as e:
            print(f"[WARNING] Failed to upload audio: {e}")

    contents.append(prompt)

    try:
        response = model.generate_content(
            contents,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.3
            }
        )
        
        result_json = json.loads(response.text)
        
        # 安全策: MIDI同期枠があれば時間をローカルデータで上書き強制補正
        if timeline_slots is not None and result_json and "timeline" in result_json:
            for idx, slot in enumerate(result_json["timeline"]):
                if idx < len(timeline_slots):
                    slot["start_time"] = timeline_slots[idx]["start_time"]
                    slot["end_time"] = timeline_slots[idx]["end_time"]
                    slot["section"] = timeline_slots[idx]["section"]
                    slot["lyrics"] = timeline_slots[idx]["lyrics"]
                    
        return result_json
    except Exception as e:
        print(f"Failed to parse Gemini response as JSON in Timeline Phase: {e}")
        return None
    finally:
        if audio_file_ref:
            try:
                genai.delete_file(audio_file_ref.name)
            except:
                pass

# =====================================================================
# 【レガシー互換用】 
# =====================================================================
def generate_initial_timeline(lyrics, bpm, duration, core_concept="", global_rules="", section_rules="", keywords="", api_key=None,
                              first_bar_offset=0.0, time_signature="4/4", split_unit="4小節ごと",
                              visual_style="特になし", aspect_ratio="16:9", audio_path=None, midi_path=None):
    """
    旧GUIや互換性のために残す1発生成関数。
    内部でステップ1（コンセプト自動生成）を行い、そのままステップ2（タイムライン生成）を実行して返す。
    """
    # 1. コンセプト生成
    concept = generate_concept_settings(
        lyrics=lyrics, bpm=bpm, duration=duration, raw_idea=core_concept, api_key=api_key, audio_path=audio_path
    )
    if not concept:
        concept = {
            "title": "My Song Project",
            "concept": core_concept if core_concept else "A beautiful music video.",
            "characters": "A protagonist.",
            "rules": global_rules if global_rules else "Cinematic visual tone."
        }
    
    # 2. タイムライン生成
    return generate_timeline_from_concept(
        lyrics=lyrics, bpm=bpm, duration=duration, concept_summary=concept, api_key=api_key,
        first_bar_offset=first_bar_offset, time_signature=time_signature,
        visual_style=visual_style, aspect_ratio=aspect_ratio, audio_path=audio_path, midi_path=midi_path
    )

def refine_image_prompt(current_prompt, user_feedback, api_key=None):
    """
    現在の画像プロンプトとユーザーからの日本語のフィードバックを元に、
    より高品質なImagen用の英語プロンプトを生成して返す。
    """
    if api_key:
        genai.configure(api_key=api_key)
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    else:
        raise ValueError("Gemini API key is not configured.")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    あなたは画像生成AI (Imagen 3/4) 用 of プロンプトエンジニアです。
    ユーザーが作成しているミュージックビデオ(MV)の1カットの画像プロンプトを、ユーザーからの修正指示に基づいてブラッシュアップしてください。

    【現在のプロンプト (英語)】
    {current_prompt}

    【ユーザーからの日本語の修正・追加指示】
    {user_feedback}

    【ブラッシュアップの条件】
    - アスペクト比は16:9を意識してください。
    - 修正指示をプロンプト内に自然に、かつ強力に反映させ、画質やディテール（ライティング、カメラアングル、質感、スタイルなど）を向上させる単語を追加して、詳細な英語の画像生成プロンプトを作成してください。
    - 応答には、ブラッシュアップした「新しい英語プロンプト」のみを出力してください。他の説明文や導入文、コードブロック用のバッククォートなどは一切不要です。
    """

    response = model.generate_content(prompt)
    return response.text.strip().replace('`', '')

def export_project_zip(project_name, timeline_data, bpm, duration, audio_path, images_dir):
    """
    タイムラインJSON、音源ファイル、および生成された画像フォルダをまとめて1つのZIPファイルのバイナリとして返す。
    """
    temp_dir = tempfile.mkdtemp()
    try:
        export_data = {
            "project_name": project_name,
            "bpm": bpm,
            "duration": duration,
            "timeline": timeline_data
        }
        json_path = os.path.join(temp_dir, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
        if audio_path and os.path.exists(audio_path):
            audio_ext = os.path.splitext(audio_path)[1]
            shutil.copy(audio_path, os.path.join(temp_dir, f"audio{audio_ext}"))
            
        zip_images_dir = os.path.join(temp_dir, "images")
        os.makedirs(zip_images_dir, exist_ok=True)
        if images_dir and os.path.exists(images_dir):
            for filename in os.listdir(images_dir):
                if filename.endswith(".png") and not filename.startswith("temp_"):
                    shutil.copy(os.path.join(images_dir, filename), os.path.join(zip_images_dir, filename))
                    
        zip_path = os.path.join(temp_dir, f"{project_name}_package")
        shutil.make_archive(zip_path, 'zip', temp_dir)
        
        with open(zip_path + ".zip", "rb") as f:
            zip_bytes = f.read()
            
        return zip_bytes
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def import_project_zip(zip_file, extract_dir, images_target_dir):
    """
    アップロードされたZIPを展開し、プロジェクトデータを復元する。
    """
    os.makedirs(extract_dir, exist_ok=True)
    os.makedirs(images_target_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    json_path = os.path.join(extract_dir, "project.json")
    if not os.path.exists(json_path):
        raise ValueError("ZIP内に project.json が見つかりません。")
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    audio_path = None
    for filename in os.listdir(extract_dir):
        if filename.startswith("audio."):
            target_audio_path = os.path.join(os.path.dirname(images_target_dir), filename)
            shutil.copy(extract_dir + "/" + filename, target_audio_path)
            audio_path = target_audio_path
            break
            
    zip_images_dir = os.path.join(extract_dir, "images")
    if os.path.exists(zip_images_dir):
        for filename in os.listdir(zip_images_dir):
            if filename.endswith(".png"):
                shutil.copy(zip_images_dir + "/" + filename, images_target_dir + "/" + filename)
                
    shutil.rmtree(extract_dir, ignore_errors=True)
    
    return {
        "project_name": data.get("project_name", "imported_project"),
        "bpm": data.get("bpm", 120.0),
        "duration": data.get("duration", 180.0),
        "timeline": data.get("timeline", []),
        "audio_path": audio_path
    }

def export_project_xlsx(project_name, timeline_data, bpm, duration, core_concept="", global_rules="", 
                        first_bar_offset=0.0, time_signature="4/4", split_unit="4小節ごと", 
                        visual_style="特なし", aspect_ratio="16:9"):
    """
    プロジェクトデータをPandasとopenpyxlを使ってスタイリングされたExcelファイル（.xlsx）のバイナリデータとして返す。
    """
    summary_data = {
        "項目": [
            "提案タイトル",
            "BPM",
            "曲の長さ (秒)",
            "世界観・コンセプト",
            "全体演出ルール",
            "1小節目開始時間 (秒)",
            "拍子",
            "分割粒度",
            "ビジュアルスタイル",
            "アスペクト比"
        ],
        "内容": [
            project_name,
            bpm,
            duration,
            core_concept,
            global_rules,
            first_bar_offset,
            time_signature,
            split_unit,
            visual_style,
            aspect_ratio
        ]
    }
    df_summary = pd.DataFrame(summary_data)
    
    timeline_rows = []
    for i, item in enumerate(timeline_data):
        timeline_rows.append({
            "Cut": i + 1,
            "section": item.get("section", ""),
            "start_time": item.get("start_time", 0.0),
            "end_time": item.get("end_time", 0.0),
            "start_time_ms": f"{int(item.get('start_time', 0.0) // 60):02d}:{item.get('start_time', 0.0) % 60:06.3f}",
            "end_time_ms": f"{int(item.get('end_time', 0.0) // 60):02d}:{item.get('end_time', 0.0) % 60:06.3f}",
            "duration": round(item.get("end_time", 0.0) - item.get("start_time", 0.0), 3),
            "lyrics": item.get("lyrics", ""),
            "description": item.get("description", ""),
            "prompt": item.get("prompt", "")
        })
    df_timeline = pd.DataFrame(timeline_rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Summary", index=False)
        df_timeline.to_excel(writer, sheet_name="Timeline", index=False)
        
        workbook = writer.book
        
        ws_summary = workbook["Summary"]
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") 
        header_font = Font(name="Meiryo UI", size=11, bold=True, color="FFFFFF")
        cell_font = Font(name="Meiryo UI", size=10)
        
        for col in range(1, 3):
            cell = ws_summary.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for row in range(2, len(df_summary) + 2):
            for col in range(1, 3):
                cell = ws_summary.cell(row=row, column=col)
                cell.font = cell_font
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                
        ws_summary.column_dimensions["A"].width = 25
        ws_summary.column_dimensions["B"].width = 60
        
        ws_timeline = workbook["Timeline"]
        
        for col in range(1, len(df_timeline.columns) + 1):
            cell = ws_timeline.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        
        for row in range(2, len(df_timeline) + 2):
            for col in range(1, len(df_timeline.columns) + 1):
                cell = ws_timeline.cell(row=row, column=col)
                cell.font = cell_font
                cell.border = thin_border
                
                col_name = df_timeline.columns[col-1]
                if col_name in ["Cut", "start_time", "end_time", "start_time_ms", "end_time_ms", "duration", "section"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                    
        for col in ws_timeline.columns:
            col_letter = get_column_letter(col[0].column)
            col_name = df_timeline.columns[col[0].column - 1]
            
            if col_name in ["lyrics", "description", "prompt"]:
                ws_timeline.column_dimensions[col_letter].width = 40
            elif col_name in ["start_time_ms", "end_time_ms"]:
                ws_timeline.column_dimensions[col_letter].width = 15
            elif col_name in ["Cut", "start_time", "end_time", "duration", "section"]:
                ws_timeline.column_dimensions[col_letter].width = 10
            else:
                ws_timeline.column_dimensions[col_letter].width = 12
                
    output.seek(0)
    return output.getvalue()
