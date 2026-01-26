#!/usr/bin/env python3
"""
Script to download gender detection model checkpoints.
Downloads OpenCV DNN models for face detection, age detection, and gender detection.
"""
import os
import urllib.request
from pathlib import Path

# Model files to download - using working URLs
MODELS = {
    "face_detector": {
        "opencv_face_detector_uint8.pb": "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/opencv_face_detector_uint8.pb",
        "opencv_face_detector.pbtxt": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/opencv_face_detector.pbtxt"
    },
    "age_detector": {
        "age_net.caffemodel": "https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/age_net.caffemodel",
        "age_deploy.prototxt": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/age_deploy.prototxt"
    },
    "gender_detector": {
        "gender_net.caffemodel": "https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/gender_net.caffemodel",
        "gender_deploy.prototxt": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/gender_deploy.prototxt"
    }
}

def download_file(url, dest_path):
    """Download a file from URL to destination path."""
    try:
        print(f"Downloading: {url}")
        print(f"  -> {dest_path}")
        urllib.request.urlretrieve(url, dest_path)
        print(f"  ✓ Downloaded successfully")
        return True
    except Exception as e:
        print(f"  ✗ Error downloading: {e}")
        return False

def main():
    """Download all required checkpoint files."""
    base_dir = Path(__file__).parent
    checkpoints_dir = base_dir / "checkpoints" / "gender_model_checkpoints"
    
    print("=" * 60)
    print("Gender Detection Model Checkpoints Downloader")
    print("=" * 60)
    print(f"Target directory: {checkpoints_dir}")
    print()
    
    # Create directory structure
    for model_type in MODELS.keys():
        model_dir = checkpoints_dir / model_type
        model_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {model_dir}")
    
    print()
    
    # Download all files
    success_count = 0
    total_count = 0
    
    for model_type, files in MODELS.items():
        print(f"\n[{model_type.upper()}]")
        model_dir = checkpoints_dir / model_type
        
        for filename, url in files.items():
            total_count += 1
            dest_path = model_dir / filename
            
            if dest_path.exists():
                print(f"  ⚠ {filename} already exists, skipping...")
                success_count += 1
            else:
                if download_file(url, dest_path):
                    success_count += 1
    
    print()
    print("=" * 60)
    print(f"Download Summary: {success_count}/{total_count} files")
    print("=" * 60)
    
    if success_count == total_count:
        print("✓ All checkpoint files downloaded successfully!")
        print("\nYou can now run:")
        print("  python test_sop_camera.py --sop-id EZA_SOP_GENDER --use-gender")
    else:
        print("⚠ Some files failed to download. Please check the errors above.")
        print("\nAlternative: You can manually download the files from:")
        print("  - OpenCV GitHub: https://github.com/opencv/opencv")
        print("  - OpenCV Extra: https://github.com/opencv/opencv_extra")

if __name__ == "__main__":
    main()
