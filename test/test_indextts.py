"""
Test script for IndexTTS2 API service
Tests health check and TTS synthesis using demo audio files.

Service URL: https://subpericranial-jameson-guessingly.ngrok-free.dev
"""

import os
import sys
import requests
from pathlib import Path
from pydub import AudioSegment

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
API_URL = "https://subpericranial-jameson-guessingly.ngrok-free.dev"
DEMO_DIR = Path(__file__).parent.parent / "demo"
OUTPUT_DIR = Path(__file__).parent / "output"

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)


def convert_to_wav(input_path: Path, output_path: Path) -> bool:
    """Convert audio file to WAV format (16kHz, mono)."""
    try:
        audio = AudioSegment.from_file(input_path)
        # Convert to mono, 16kHz for best TTS results
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(output_path, format="wav")
        print(f"✅ Converted: {input_path.name} -> {output_path.name}")
        return True
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return False


def test_health_check():
    """Test the health check endpoint."""
    print("\n" + "="*60)
    print("🩺 Testing Health Check Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{API_URL}/api/health", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Health check passed!")
        print(f"   Status: {data.get('status', 'unknown')}")
        print(f"   Model: {data.get('model', 'unknown')}")
        print(f"   Device: {data.get('device', 'unknown')}")
        print(f"   Loaded: {data.get('loaded', False)}")
        return True
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection failed: {e}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_tts_synthesis(text: str, ref_audio_path: Path, output_name: str, emo_alpha: float = 1.0):
    """Test TTS synthesis with given parameters."""
    print(f"\n🎙️ Testing TTS: {output_name}")
    print(f"   Text: {text[:50]}...")
    print(f"   Reference: {ref_audio_path.name}")
    print(f"   Emo Alpha: {emo_alpha}")
    
    output_path = OUTPUT_DIR / f"{output_name}.wav"
    
    try:
        with open(ref_audio_path, 'rb') as audio_file:
            files = {
                'spk_audio': (ref_audio_path.name, audio_file, 'audio/wav')
            }
            data = {
                'text': text,
                'emo_alpha': str(emo_alpha)
            }
            
            response = requests.post(
                f"{API_URL}/api/tts",
                files=files,
                data=data,
                timeout=120
            )
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            file_size = output_path.stat().st_size / 1024  # KB
            print(f"✅ Success! Output: {output_path.name} ({file_size:.1f} KB)")
            return True
            
        elif response.status_code == 503:
            error_data = response.json()
            print(f"❌ Model not loaded: {error_data.get('error', 'Unknown')}")
            return False
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
            except:
                error_msg = response.text or f"HTTP {response.status_code}"
            print(f"❌ API Error: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ TTS failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 IndexTTS2 API Test Suite")
    print(f"   API URL: {API_URL}")
    print(f"   Demo Dir: {DEMO_DIR}")
    print(f"   Output Dir: {OUTPUT_DIR}")
    
    results = []
    
    # Test 1: Health Check
    results.append(("Health Check", test_health_check()))
    
    # Prepare reference audio
    print("\n" + "="*60)
    print("📀 Preparing Reference Audio")
    print("="*60)
    
    demo_audio = DEMO_DIR / "demo-rzdf.mp3"
    ref_audio_wav = OUTPUT_DIR / "reference.wav"
    
    if not demo_audio.exists():
        print(f"❌ Demo audio not found: {demo_audio}")
        results.append(("Audio Preparation", False))
    else:
        print(f"Found demo audio: {demo_audio.name}")
        success = convert_to_wav(demo_audio, ref_audio_wav)
        results.append(("Audio Preparation", success))
        
        if success:
            # Test 2: Basic TTS (Chinese)
            results.append((
                "TTS Chinese (emo=1.0)",
                test_tts_synthesis(
                    "你好，这是一个语音合成测试。Hello, this is a voice synthesis test.",
                    ref_audio_wav,
                    "test_chinese_default",
                    emo_alpha=1.0
                )
            ))
            
            # Test 3: TTS with different emotion values
            results.append((
                "TTS Emo Alpha 0.5 (Calm)",
                test_tts_synthesis(
                    "今天天气真好，我想去公园散步。",
                    ref_audio_wav,
                    "test_calm",
                    emo_alpha=0.5
                )
            ))
            
            results.append((
                "TTS Emo Alpha 1.5 (Emotional)",
                test_tts_synthesis(
                    "这是一个非常令人兴奋的消息！",
                    ref_audio_wav,
                    "test_emotional",
                    emo_alpha=1.5
                )
            ))
            
            # Test 4: English TTS
            results.append((
                "TTS English",
                test_tts_synthesis(
                    "Welcome to VideoLingo! This is an amazing tool for video translation.",
                    ref_audio_wav,
                    "test_english",
                    emo_alpha=1.0
                )
            ))
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
