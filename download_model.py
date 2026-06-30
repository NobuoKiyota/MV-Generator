import sys
import os

def main():
    print("===================================================")
    print("   Stable Diffusion モデル (DreamShaper-8) をロード中...   ")
    print("===================================================")
    
    try:
        import torch
        from diffusers import StableDiffusionPipeline
        
        # GPU/CPU判定
        if not torch.cuda.is_available():
            print("[WARNING] CUDA が利用できません。CPUモードで実行します。")
            device = "cpu"
            dtype = torch.float32
        else:
            print("[INFO] CUDA (GPU) が検出されました。")
            device = "cuda"
            dtype = torch.float16
            
        local_model_path = os.path.join("models", "dreamshaper_8.safetensors")
        
        if os.path.exists(local_model_path):
            print(f"[INFO] ローカルモデルファイルを検出しました: {local_model_path}")
            print("[INFO] ローカルファイルからオフラインロードを開始します...")
            pipe = StableDiffusionPipeline.from_single_file(
                local_model_path,
                torch_dtype=dtype,
                safety_checker=None
            )
            print("[INFO] モデルの動作確認を実行しています...")
            pipe = pipe.to(device)
            print("[SUCCESS] ローカルモデルファイルの読み込みと動作確認に成功しました！")
        else:
            print(f"[INFO] ローカルファイルが {local_model_path} に見つかりません。")
            print("[INFO] Hugging Face からの自動ダウンロード（約2GB）を試みます...")
            
            from huggingface_hub import enable_progress_bars
            enable_progress_bars()
            
            model_id = "Lykon/dreamshaper-8"
            pipe = StableDiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype,
                safety_checker=None
            )
            print("[INFO] モデルの動作確認を実行しています...")
            pipe = pipe.to(device)
            print("[SUCCESS] モデルの自動ダウンロードと動作確認に成功しました！")
            
    except Exception as e:
        print(f"[ERROR] モデルのロードまたは初期化中にエラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
