import os
import sys
import argparse
from PIL import Image

def generate_image(prompt, output_path):
    """
    画像生成のメイン処理 (コマンドライン版)。
    ローカルのGPU（Stable Diffusion: DreamShaper-8）を使用して画像を生成します。
    CUDAが利用できない場合は、CPUに自動フォールバックして生成を実行します。
    """
    try:
        import torch
        from diffusers import StableDiffusionPipeline
        
        # CUDAの有無によるデバイスおよびデータ型の決定
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        
        print(f"[ImageGen] Device selected: {device.upper()} (CUDA Available: {torch.cuda.is_available()})")
        if device == "cpu":
            print("[ImageGen] WARNING: Running on CPU. This will be very slow (may take 1-3 minutes).")
            print("[ImageGen] To enable GPU speedup, install CUDA-enabled PyTorch inside your venv.")
            
        local_model_path = os.path.join("models", "dreamshaper_8.safetensors")
        if os.path.exists(local_model_path):
            print(f"[ImageGen] Found local model file at {local_model_path}. Loading offline...")
            pipe = StableDiffusionPipeline.from_single_file(
                local_model_path,
                torch_dtype=dtype,
                safety_checker=None
            )
        else:
            print(f"[ImageGen] Local file not found at {local_model_path}. Downloading from Hugging Face...")
            model_id = "Lykon/dreamshaper-8"
            pipe = StableDiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype,
                safety_checker=None
            )
            
        pipe = pipe.to(device)
        pipe.enable_attention_slicing()
        
        print(f"[ImageGen] Generating image on {device.upper()} with prompt: {prompt}")
        image = pipe(
            prompt=prompt,
            width=1024,
            height=576,
            num_inference_steps=20
        ).images[0]
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        image.save(output_path)
        print(f"[ImageGen] Successfully generated and saved image locally to {output_path}")
        
        status = "LOCAL_SUCCESS" if device == "cuda" else "CPU_SUCCESS"
        return True, status

    except Exception as e:
        error_msg = str(e)
        print(f"[ImageGen] Generation failed: {error_msg}")
        return False, error_msg

def main():
    parser = argparse.ArgumentParser(description="Generate image using Stable Diffusion (GPU/CPU).")
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--output_path", required=True, help="Path to save generated image")
    parser.add_argument("--api_key", default=None, help="Gemini API Key (ignored)")
    args = parser.parse_args()
    
    success, status = generate_image(args.prompt, args.output_path)
    if success:
        print(f"STATUS:{status}")
        sys.exit(0)
    else:
        print(f"STATUS:FAILED_{status}")
        sys.exit(1)

if __name__ == "__main__":
    main()
