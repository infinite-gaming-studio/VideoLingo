#!/usr/bin/env python3
"""
VideoLingo Cloud Native Environment Checker

This script checks if the environment is properly configured for Cloud Native Mode.
It verifies:
1. Cloud service connectivity
2. Required dependencies (lightweight)
3. Configuration settings

Usage:
    python check_cloud_native.py

Exit codes:
    0 - All checks passed
    1 - Configuration error
    2 - Connection error
    3 - Missing dependencies
"""

import sys
import os

def print_header(text):
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def print_info(text):
    print(f"ℹ️  {text}")

def check_dependencies():
    """Check if required lightweight dependencies are installed"""
    print_header("Checking Dependencies")
    
    required = {
        'requests': 'HTTP client for cloud API',
        'pydub': 'Audio processing',
        'pandas': 'Data manipulation',
        'numpy': 'Numerical computing',
        'pyyaml': 'YAML config parsing',
        'rich': 'Terminal output formatting',
        'moviepy': 'Video processing',
        'cv2': 'OpenCV for image processing',
        'spacy': 'NLP processing',
        'streamlit': 'Web UI (optional)',
    }
    
    missing = []
    for module, description in required.items():
        try:
            if module == 'cv2':
                __import__('cv2')
            else:
                __import__(module)
            print_success(f"{module:12} - {description}")
        except ImportError:
            print_error(f"{module:12} - {description}")
            missing.append(module)
    
    if missing:
        print("\n" + "="*60)
        print_error(f"Missing {len(missing)} required dependencies")
        print("\nInstall with:")
        print("  pip install -r requirements_cloud.txt")
        print("="*60)
        return False
    
    print_success("All required dependencies are installed")
    return True

def check_heavy_dependencies():
    """Check if heavy GPU dependencies are present (should NOT be in cloud native)"""
    print_header("Checking for Heavy Dependencies (Should NOT be present)")
    
    heavy_deps = {
        'torch': 'PyTorch (GPU)',
        'whisperx': 'WhisperX ASR',
        'demucs': 'Demucs separation',
        'ctranslate2': 'Translation engine',
        'transformers': 'HuggingFace transformers',
        'pytorch_lightning': 'PyTorch Lightning',
        'lightning': 'Lightning framework',
    }
    
    found = []
    for module, description in heavy_deps.items():
        try:
            __import__(module)
            print_warning(f"{module:20} - {description} (should be removed in cloud native mode)")
            found.append(module)
        except ImportError:
            print_success(f"{module:20} - {description} (correctly absent)")
    
    if found:
        print("\n" + "="*60)
        print_warning(f"Found {len(found)} heavy dependencies")
        print("\nThese should be removed in Cloud Native Mode:")
        print("  pip uninstall torch torchaudio whisperx demucs ctranslate2")
        print("="*60)
    else:
        print_success("No heavy GPU dependencies found (correct for cloud native)")
    
    return True

def check_config():
    """Check configuration settings"""
    print_header("Checking Configuration")
    
    try:
        from core.utils import load_key
        
        # Check cloud native settings
        cloud_native_enabled = load_key("cloud_native.enabled", False)
        cloud_url = load_key("cloud_native.cloud_url", "")
        
        print_info(f"Cloud Native Mode: {'ENABLED' if cloud_native_enabled else 'DISABLED'}")
        
        if cloud_native_enabled:
            if not cloud_url:
                print_error("cloud_native.cloud_url is not configured")
                print("\nPlease add to config.yaml:")
                print("  cloud_native:")
                print("    enabled: true")
                print("    cloud_url: 'https://your-cloud-server.ngrok-free.app'")
                return False
            else:
                print_success(f"Cloud URL configured: {cloud_url}")
        else:
            print_warning("Cloud Native Mode is disabled")
            print_info("To enable, set cloud_native.enabled: true in config.yaml")
        
        # Check whisper settings
        whisper_runtime = load_key("whisper.runtime", "local")
        print_info(f"Whisper runtime: {whisper_runtime}")
        
        if cloud_native_enabled and whisper_runtime != "local":
            print_warning(f"In Cloud Native Mode, whisper.runtime should be 'local' (cloud processing is handled automatically)")
        
        # Check demucs settings
        demucs_enabled = load_key("demucs", False)
        print_info(f"Demucs enabled: {demucs_enabled}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to read configuration: {e}")
        return False

def check_cloud_connection():
    """Check connection to cloud service"""
    print_header("Checking Cloud Service Connection")
    
    try:
        from core.utils import load_key
        
        cloud_native_enabled = load_key("cloud_native.enabled", False)
        if not cloud_native_enabled:
            print_info("Cloud Native Mode is disabled, skipping connection check")
            return True
        
        cloud_url = load_key("cloud_native.cloud_url", "")
        if not cloud_url:
            print_error("No cloud URL configured")
            return False
        
        # Try to connect
        try:
            from whisperx_cloud.unified_client import check_cloud_connection as check_cloud
            result = check_cloud(cloud_url)
            
            if result.get('available'):
                print_success(f"Successfully connected to cloud service at {cloud_url}")
                print_info(f"Platform: {result.get('platform', 'unknown')}")
                print_info(f"Device: {result.get('device', 'unknown')}")
                
                services = result.get('services', {})
                for svc_name, svc_info in services.items():
                    status = "✅ Available" if svc_info.get('available') else "❌ Unavailable"
                    print(f"  {status} - {svc_name}")
                
                return True
            else:
                print_error(f"Cloud service is not available")
                print_error(f"Error: {result.get('error', 'Unknown error')}")
                return False
                
        except ImportError:
            print_error("Cannot import whisperx_cloud module")
            print_info("Make sure whisperx_cloud/ directory is in the project root")
            return False
            
    except Exception as e:
        print_error(f"Failed to check cloud connection: {e}")
        return False

def main():
    print_header("VideoLingo Cloud Native Environment Checker")
    print()
    print("This script checks if your environment is properly configured")
    print("for Cloud Native Mode (CPU-only with remote GPU services)")
    print()
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Heavy Dependencies", check_heavy_dependencies),
        ("Configuration", check_config),
        ("Cloud Connection", check_cloud_connection),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Check failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print_header("Summary")
    
    all_passed = all(result for _, result in results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    if all_passed:
        print("="*60)
        print_success("All checks passed! Environment is ready for Cloud Native Mode.")
        print("="*60)
        print()
        print("To start using VideoLingo in Cloud Native Mode:")
        print("  1. Ensure your cloud server is running (whisperx_cloud/unified_server.py)")
        print("  2. Run: streamlit run st.py")
        print()
        return 0
    else:
        print("="*60)
        print_error("Some checks failed. Please fix the issues above.")
        print("="*60)
        print()
        print("For Cloud Native Mode setup guide, see:")
        print("  - CLOUD_NATIVE_DESIGN.md")
        print("  - whisperx_cloud/README.md")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
