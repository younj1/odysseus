"""Export a fine-tuned model to Ollama."""

import os
import sys
import subprocess


def export_to_gguf(
    model_dir: str = "data/finetune_output/merged",
    output_path: str = "data/finetune_output/aria-custom.gguf",
    quantize: str = "q4_k_m",
) -> str:
    """Convert merged model to GGUF format for Ollama."""
    
    print(f"Converting {model_dir} to GGUF...")
    print(f"Quantization: {quantize}")
    
    # Check if llama.cpp convert script exists
    convert_script = os.path.expanduser("~/llama.cpp/convert_hf_to_gguf.py")
    if not os.path.exists(convert_script):
        print("\nllama.cpp not found. Install it first:")
        print("  git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp")
        print("  cd ~/llama.cpp && make")
        return ""
    
    # Convert
    cmd = [
        sys.executable, convert_script,
        model_dir,
        "--outfile", output_path,
        "--outtype", quantize,
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\nGGUF model saved: {output_path}")
        print(f"\nNext steps:")
        print(f"  1. Create Modelfile: python aria/finetune/train.py")
        print(f"  2. Import to Ollama: ollama create aria-custom -f data/finetune_output/Modelfile")
        print(f"  3. Test: ollama run aria-custom")
        return output_path
    else:
        print(f"Conversion failed: {result.stderr}")
        return ""


if __name__ == "__main__":
    export_to_gguf()
