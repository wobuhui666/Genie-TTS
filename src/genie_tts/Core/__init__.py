import importlib
import ctypes
from pathlib import Path
import sys
import os

try:
    onnxruntime = importlib.import_module("onnxruntime")
except ImportError:
    raise ImportError("onnxruntime is required to use this module.")

ort_dir = Path(onnxruntime.__file__).parent / "capi"
version = onnxruntime.__version__

if sys.platform.startswith("linux"):
    libname = "libonnxruntime.so." + version
    mode = 0
    if hasattr(ctypes, "RTLD_NOW"):
        mode |= ctypes.RTLD_NOW
    if hasattr(ctypes, "RTLD_GLOBAL"):
        mode |= ctypes.RTLD_GLOBAL
    lib_path = os.path.join(ort_dir, libname)
    ctypes.CDLL(lib_path, mode=mode)
    
elif sys.platform == "darwin":
    # macOS
    libname = "libonnxruntime.dylib"
    lib_path = os.path.join(ort_dir, libname)
    ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
    
elif sys.platform.startswith("win"):
    # Windows
    libname = "onnxruntime.dll"
    lib_path = os.path.join(ort_dir, libname)
    ctypes.WinDLL(lib_path)
    
else:
    raise RuntimeError(f"Unsupported platform: {sys.platform}")