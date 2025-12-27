#!/usr/bin/env python3
"""
Model Conversion Script
=======================
This script downloads and converts PyTorch models to ONNX format.
"""

import os
import sys

def main():
    print("Starting ONNX conversion...")
    
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
