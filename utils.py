import os
import json
import librosa
import google.generativeai as genai
from dotenv import load_dotenv
import re

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

def save_project(filepath, data):
    """プロジェクトデータをJSONファイルとして保存する"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving project: {e}")
        return False

def load_project(filepath):
    """プロジェクトデータをJSONファイルから読み込む"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading project: {e}")
        return None

def analyze_audio(audio_path):
    """音声ファイルを解析してBPMと曲の長さを返す"""
    try:
        y, sr = librosa.load(audio_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        
        # BPMの推定
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        
        # テンポ（BPM）はfloatまたはarrayで返るため数値に変換
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

def generate_initial_timeline(lyrics, bpm, duration, core_concept, global_rules, section_rules, keywords, api_key=None):
    """Gemini APIを呼び出し、歌詞・世界観・ルール・テンポからタイムラインを自動生成する"""
    if api_key:
        genai.configure(api_key=api_key)
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    else:
        raise ValueError("Gemini API key is not configured.")

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 歌詞を構造化データとしてパース
    structured_lyrics = parse_tagged_lyrics(lyrics)
    lyrics_json_str = json.dumps(structured_lyrics, indent=2, ensure_ascii=False)
    
    prompt = f"""
あなたはプロのミュージックビデオ(MV)監督および映像プランナーです。
入力データと各種ルール、制約事項を元に、曲全体のカット割り（タイムライン）を高度に設計してください。

【入力データ】
- 構造化された歌詞リスト (セクションごとの分割):
```json
{lyrics_json_str}
```
- テンポ (BPM): {bpm}
- 全体の長さ: {duration}秒

【映像演出・プロット設定（重要度別）】

1. [最優先事項] 絶対に崩したくない世界観・キャラクター設定:
\"\"\"
{core_concept}
\"\"\"
※この設定はすべてのカットにおける画像生成プロンプトや描写で厳格に維持してください。

2. [優先事項] 全体を通した演出ルール・盛り上がり制御:
\"\"\"
{global_rules}
\"\"\"
※サビ（Chorus）部分での盛り上げ方や、全体的なカメラワークの統一感など、構成上の指示を守ってください。

3. [推奨事項] セクションごとの個別ルール:
\"\"\"
{section_rules}
\"\"\"
※イントロ、メロ、サビなど、特定のセクションに対する指示があれば適用してください。

4. [任意項目] 取り入れてほしい象徴的なキーワード:
\"\"\"
{keywords}
\"\"\"
※これらのキーワードを、映像のメタファーや背景アセットとして適宜カットに散りばめてください。

【設計の条件】
1. 【最重要】人間が指定した「構造化された歌詞リスト」の各セクションの並び順と構造を必ず遵守してください。AIが勝手に歌詞のセクション構成を崩したり、順番を入れ替えたりしないでください。
2. 曲全体の長さ（0.0秒から{duration}秒まで）をカバーするようにセクション（Intro, A-Melody, Chorus, Outro等）を定義し、さらにそれぞれのセクションをいくつかの「カット（Cut）」に分割してください。
3. 各カットの切り替えタイミングは、BPM（1拍の長さは {60.0/bpm:.4f} 秒、1小節4拍なら {240.0/bpm:.4f} 秒）を考慮し、できるだけ小節の区切りやキリの良い秒数（例: 2.0秒、4.0秒、8.0秒間隔など）で切り替わるように設計してください。
4. 各カットに対して、以下を設計してください。
   - section: セクション名（入力された歌詞リストのセクション名をそのまま引き継ぐ）
   - start_time: カット開始秒数 (0.0 からスタート)
   - end_time: カット終了秒数 (最後は必ず {duration} 秒になるように)
   - lyrics: そのカットに対応する歌詞（そのセクションの歌詞をさらに細分化して割り当てる。歌詞がない部分は空文字）
   - description: 映像の具体的な演出・カメラワーク・被写体の動きの説明（日本語）。上記の「世界観」や「演出ルール」を反映させてください。
   - prompt: 後の画像生成AI (Imagen 3等) で入力するための、具体的かつ高品質な英語の画像生成プロンプト。アスペクト比は16:9を想定し、上記で指定された世界観・キャラクター・ルール・キーワードを高度に反映・ブレンドしてください。

必ず以下のJSONスキーマに従って結果を返してください。JSON以外の文章は一切出力しないでください。

【出力フォーマット (JSON)】
{{
  "bpm": {bpm},
  "duration": {duration},
  "timeline": [
    {{
      "section": "セクション名",
      "start_time": 0.0,
      "end_time": 4.0,
      "lyrics": "歌詞の一節",
      "description": "演出・カメラワークの詳細な日本語説明",
      "prompt": "Highly detailed image generation prompt in English, 16:9, matching the style and rules"
    }}
  ]
}}
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.3
        }
    )
    
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response as JSON: {e}")
        print("Raw response:", response.text)
        return None

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
あなたは画像生成AI (Imagen 3/4) 用のプロンプトエンジニアです。
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

import zipfile
import shutil
import tempfile

def export_project_zip(project_name, timeline_data, bpm, duration, audio_path, images_dir):
    """
    タイムラインJSON、音源ファイル、および生成された画像フォルダをまとめて1つのZIPファイルのバイナリとして返す。
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. JSONの作成
        export_data = {
            "project_name": project_name,
            "bpm": bpm,
            "duration": duration,
            "timeline": timeline_data
        }
        json_path = os.path.join(temp_dir, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
        # 2. 音源のコピー
        if audio_path and os.path.exists(audio_path):
            audio_ext = os.path.splitext(audio_path)[1]
            shutil.copy(audio_path, os.path.join(temp_dir, f"audio{audio_ext}"))
            
        # 3. 画像のコピー
        zip_images_dir = os.path.join(temp_dir, "images")
        os.makedirs(zip_images_dir, exist_ok=True)
        if images_dir and os.path.exists(images_dir):
            for filename in os.listdir(images_dir):
                if filename.endswith(".png") and not filename.startswith("temp_"):
                    shutil.copy(os.path.join(images_dir, filename), os.path.join(zip_images_dir, filename))
                    
        # 4. ZIP化
        zip_path = os.path.join(temp_dir, f"{project_name}_package")
        shutil.make_archive(zip_path, 'zip', temp_dir)
        
        # 5. バイナリの読み込み
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
    
    # メモリ上のZIPを展開
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    # project.json の読み込み
    json_path = os.path.join(extract_dir, "project.json")
    if not os.path.exists(json_path):
        raise ValueError("ZIP内に project.json が見見つかりません。")
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 音源の復元とパス設定
    audio_path = None
    for filename in os.listdir(extract_dir):
        if filename.startswith("audio."):
            target_audio_path = os.path.join(os.path.dirname(images_target_dir), filename)
            shutil.copy(os.path.join(extract_dir, filename), target_audio_path)
            audio_path = target_audio_path
            break
            
    # 画像の復元
    zip_images_dir = os.path.join(extract_dir, "images")
    if os.path.exists(zip_images_dir):
        for filename in os.listdir(zip_images_dir):
            if filename.endswith(".png"):
                shutil.copy(os.path.join(zip_images_dir, filename), os.path.join(images_target_dir, filename))
                
    shutil.rmtree(extract_dir, ignore_errors=True)
    
    return {
        "project_name": data.get("project_name", "imported_project"),
        "bpm": data.get("bpm", 120.0),
        "duration": data.get("duration", 180.0),
        "timeline": data.get("timeline", []),
        "audio_path": audio_path
    }



