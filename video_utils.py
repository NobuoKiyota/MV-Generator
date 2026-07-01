import os
import time
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# ローカル Stable Diffusion パイプラインキャッシュ用
_sd_pipeline = None

def generate_imagen_image(prompt, output_path, api_key=None, log_callback=None):
    """
    画像生成のメイン処理。
    `generate_image_cmd.py` を別プロセスとして呼び出します。これにより、画像生成終了時に
    GPU VRAMやメモリが完全に解放され、StreamlitのWebSocket通信がフリーズするのを防ぎます。
    """
    import sys
    import subprocess
    
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "generate_image_cmd.py"),
        "--prompt", prompt,
        "--output_path", output_path
    ]
    if api_key:
        cmd.extend(["--api_key", api_key])
        
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        # Popenを使ってリアルタイムに出力を読み取る
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        status_msg = "UNKNOWN"
        while True:
            line = process.stdout.readline()
            if not line:
                break
            line_str = line.strip()
            print(f"[ImageGen] {line_str}")
            if log_callback:
                log_callback(line_str)
                
            # 出力からステータスコードを抽出
            if "STATUS:" in line_str:
                status_msg = line_str.split("STATUS:")[1].strip()
                
        rc = process.wait()
        
        if rc == 0:
            if status_msg == "LOCAL_SUCCESS":
                return True, "LOCAL_SUCCESS"
            elif status_msg == "CLOUD_SUCCESS":
                return True, "CLOUD_SUCCESS"
            else:
                return True, status_msg
        else:
            if "FAILED_PAID_PLAN_REQUIRED" in status_msg:
                return False, "PAID_PLAN_REQUIRED"
            elif "FAILED_" in status_msg:
                return False, status_msg.replace("FAILED_", "")
            else:
                return False, f"プロセスが終了コード {rc} で終了しました。{status_msg}"
                
    except Exception as e:
        print(f"Error executing generate_image_cmd.py: {e}")
        return False, str(e)


def create_text_placeholder(text, section, duration, output_path, size=(1024, 576)):
    """
    画像がないカット用に、歌詞テキストとセクション名が描かれた黒背景画像を一時生成して保存する。
    """
    try:
        # 背景色（ダークグレー/紺）
        img = Image.new('RGB', size, color=(20, 24, 33))
        draw = ImageDraw.Draw(img)
        
        # Windowsの日本語標準フォント（メイリオまたはMSゴシック）のロード試行
        font_path = "C:\\Windows\\Fonts\\meiryo.ttc"
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\msgothic.ttc"
            
        try:
            font_section = ImageFont.truetype(font_path, 36) if os.path.exists(font_path) else ImageFont.load_default()
            font_lyrics = ImageFont.truetype(font_path, 24) if os.path.exists(font_path) else ImageFont.load_default()
            font_duration = ImageFont.truetype(font_path, 18) if os.path.exists(font_path) else ImageFont.load_default()
        except Exception:
            font_section = ImageFont.load_default()
            font_lyrics = ImageFont.load_default()
            font_duration = ImageFont.load_default()
            
        # 描画テキストの準備
        sec_text = f"[{section}]"
        lyr_text = text if text else "(インスト / 間奏)"
        dur_text = f"Duration: {duration:.2f}s"
        
        # テキストの描画位置 (中央寄せ)
        # セクション名
        draw.text((50, 100), sec_text, fill=(0, 200, 255), font=font_section) # 青色ネオン調
        
        # 歌詞テキスト（長い場合は簡易改行、ここでは簡易的に中央付近）
        draw.text((50, 240), lyr_text, fill=(240, 240, 240), font=font_lyrics)
        
        # デュレーション
        draw.text((50, 480), dur_text, fill=(120, 120, 120), font=font_duration)
        
        # 格子状のグリッド線を薄く描画して寂しさを軽減（Vコンテ感の演出）
        for y in range(0, size[1], 100):
            draw.line([(0, y), (size[0], y)], fill=(35, 40, 50), width=1)
        for x in range(0, size[0], 100):
            draw.line([(x, 0), (x, size[1])], fill=(35, 40, 50), width=1)
            
        # 保存
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path)
        return True
    except Exception as e:
        print(f"Error creating text placeholder: {e}")
        return False

def build_slideshow(timeline, audio_path, output_path, images_dir):
    """
    タイムラインと画像フォルダを受け取り、スライドショー動画を結合して音源とマージする。
    画像が欠けているカットは、一時的にプレースホルダー画像を自動生成して繋ぎ合わせる。
    """
    clips = []
    temp_files = []
    
    print(f"Starting slideshow compilation for {len(timeline)} cuts...")
    
    try:
        for i, cut in enumerate(timeline):
            start = float(cut.get("start_time", 0.0))
            end = float(cut.get("end_time", 0.0))
            duration = end - start
            if duration <= 0:
                continue
                
            section = cut.get("section", "N/A")
            lyrics = cut.get("lyrics", "")
            
            # 画像ファイルの検索
            img_filename = f"cut_{i}.png"
            img_path = os.path.join(images_dir, img_filename)
            
            # もし画像が存在しない場合はプレースホルダーを作成
            if not os.path.exists(img_path):
                temp_placeholder_path = os.path.join(images_dir, f"temp_placeholder_{i}.png")
                create_text_placeholder(lyrics, section, duration, temp_placeholder_path)
                target_img_path = temp_placeholder_path
                temp_files.append(temp_placeholder_path)
            else:
                target_img_path = img_path
                
            # ImageClipの作成と時間設定
            clip = ImageClip(target_img_path).set_duration(duration)
            clips.append(clip)
            
        if not clips:
            raise ValueError("No valid timeline cuts to render.")
            
        # クリップの連結
        print("Concatenating video clips...")
        video = concatenate_videoclips(clips, method="compose")
        
        # 音声の紐付け
        if audio_path and os.path.exists(audio_path):
            print(f"Adding audio track from: {audio_path}")
            audio = AudioFileClip(audio_path)
            
            # 音声の長さとビデオの長さを合わせる（短い方に合わせる）
            final_duration = min(video.duration, audio.duration)
            video = video.set_duration(final_duration)
            audio = audio.subclip(0, final_duration)
            
            video = video.set_audio(audio)
            
        # 出力ディレクトリの作成
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 動画の書き出し (高速化最適化版)
        print(f"Rendering final video to {output_path}...")
        video.write_videofile(
            output_path, 
            fps=2,                # 静止画スライドショーなので低fpsで必要十分。エンコード速度を劇的に向上
            codec="libx264", 
            audio_codec="aac",
            preset="ultrafast",   # エンコードプリセットを最速に設定
            threads=4,            # CPUマルチスレッドを明示的に使用
            temp_audiofile=os.path.join(images_dir, "temp_audio.mp3"),
            remove_temp=True
        )
        print("Rendering complete!")
        return True
        
    except Exception as e:
        print(f"Error building slideshow: {e}")
        return False
        
    finally:
        # 一時生成したプレースホルダー画像のクリーンアップ
        print("Cleaning up temporary placeholder images...")
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                print(f"Failed to delete temp file {temp_file}: {e}")
