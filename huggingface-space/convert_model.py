#!/usr/bin/env python3
"""
Model Conversion Script
=======================
This script downloads GenieData resources and converts PyTorch models to ONNX format.
"""

import os
import sys

def download_genie_data():
    """Download GenieData resources from HuggingFace"""
    from huggingface_hub import snapshot_download
    
    genie_data_dir = os.environ.get("GENIE_DATA_DIR", "./GenieData")
    
    if os.path.exists(genie_data_dir) and os.listdir(genie_data_dir):
        print(f"GenieData already exists at {genie_data_dir}")
        return
    
    print("🚀 Starting download Genie-TTS resources from HuggingFace...")
    snapshot_download(
        repo_id="High-Logic/Genie",
        repo_type="model",
        allow_patterns="GenieData/*",
        local_dir=".",
        local_dir_use_symlinks=False,  # Don't use symlinks in Docker
    )
    print("✅ Genie-TTS resources downloaded successfully.")

def main():
    # Set environment variable for GenieData location BEFORE importing genie_tts
    os.environ["GENIE_DATA_DIR"] = "/app/GenieData"
    
    # Step 1: Download GenieData resources
    print("Step 1: Downloading GenieData resources...")
    download_genie_data()
    
    # Step 2: Now import genie_tts (it will check for GenieData)
    print("Step 2: Starting ONNX conversion...")
    import genie_tts as genie
    
    ckpt_path = os.environ.get("CKPT_PATH", "/app/temp/model.ckpt")
    pth_path = os.environ.get("PTH_PATH", "/app/temp/model.pth")
    output_dir = os.environ.get("OUTPUT_DIR", "/app/models/liang/onnx")
    
    print(f"CKPT path: {ckpt_path}")
    print(f"PTH path: {pth_path}")
    print(f"Output dir: {output_dir}")
    
    # Check if files exist
    if not os.path.exists(ckpt_path):
        print(f"Error: CKPT file not found: {ckpt_path}")
        sys.exit(1)
    
    if not os.path.exists(pth_path):
        print(f"Error: PTH file not found: {pth_path}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert model
    genie.convert_to_onnx(
        torch_ckpt_path=ckpt_path,
        torch_pth_path=pth_path,
        output_dir=output_dir
    )
    
    print("ONNX conversion complete!")


if __name__ == "__main__":
    main()
