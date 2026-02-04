"""
测试远程 WhisperX Cloud 服务
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from whisperx_cloud.whisperx_cloud_client import (
    WhisperXCloudClient,
    check_cloud_connection,
    get_server_info,
    transcribe_audio_cloud
)
from rich import print as rprint

# 云服务 URL
CLOUD_URL = 'https://adiaphoristic-zaire-reminiscently.ngrok-free.dev'

# 测试视频路径
VIDEO_FILE = '/Users/nvozi/Coding/ai-based-projects/VideoLingo/demo/bilibili_BV1FZ4y1i78V_852x480.mp4'

# 输出目录
OUTPUT_DIR = project_root / 'demo' / 'test_output'
OUTPUT_DIR.mkdir(exist_ok=True)


def convert_video_to_audio(video_file: str, output_audio: str) -> str:
    """使用 ffmpeg 将视频转换为音频"""
    rprint(f"[blue]🎬➡️🎵 转换视频到音频...[/blue]")
    
    cmd = [
        'ffmpeg', '-y', '-i', video_file,
        '-vn',  # 无视频
        '-c:a', 'libmp3lame',  # MP3 编码
        '-b:a', '32k',  # 比特率
        '-ar', '16000',  # 采样率
        '-ac', '1',  # 单声道
        '-metadata', 'encoding=UTF-8',
        output_audio
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        rprint(f"[red]❌ FFmpeg 错误:[/red] {result.stderr}")
        raise RuntimeError("视频转换失败")
    
    rprint(f"[green]✅ 音频已保存:[/green] {output_audio}")
    return output_audio


def test_health_check():
    """测试服务健康检查"""
    rprint("\n[bold cyan]=== 1. 健康检查 ===[/bold cyan]\n")

    client = WhisperXCloudClient(CLOUD_URL)

    try:
        health = client.health_check()
        rprint("[green]✅ 服务状态:[/green]")
        rprint(f"   服务器版本: {health.get('server_version', 'unknown')}")
        rprint(f"   平台: {health.get('platform', 'unknown')}")
        rprint(f"   设备: {health.get('device', 'unknown')}")
        rprint(f"   GPU 内存: {health.get('gpu_memory_gb', 0):.2f} GB")
        return True
    except Exception as e:
        rprint(f"[red]❌ 健康检查失败:[/red] {e}")
        return False


def test_connection():
    """测试连接"""
    rprint("\n[bold cyan]=== 2. 连接测试 ===[/bold cyan]\n")
    
    result = check_cloud_connection(CLOUD_URL)
    
    if result['available']:
        rprint("[green]✅ 连接成功![/green]")
        rprint(f"   平台: {result.get('platform', 'unknown')}")
        rprint(f"   设备: {result.get('device', 'unknown')}")
        if result.get('gpu_memory_gb'):
            rprint(f"   GPU 内存: {result['gpu_memory_gb']:.2f} GB")
        return True
    else:
        rprint(f"[red]❌ 连接失败:[/red] {result.get('error')}")
        return False


def test_transcribe_simple():
    """简单转录测试 - 直接使用 WhisperXCloudClient"""
    rprint("\n[bold cyan]=== 3. 简单转录测试 (使用 WhisperXCloudClient) ===[/bold cyan]\n")
    
    # 转换视频为音频
    audio_file = OUTPUT_DIR / 'test_audio.mp3'
    convert_video_to_audio(VIDEO_FILE, str(audio_file))
    
    # 创建客户端
    client = WhisperXCloudClient(CLOUD_URL)
    
    # 转录音频
    rprint(f"[blue]🎯 开始转录...[/blue]")
    
    try:
        result = client.transcribe(
            audio_path=str(audio_file),
            language=None,  # 自动检测
            model='large-v3',
            align=True,
            speaker_diarization=False,
            timeout=600
        )
        
        rprint("\n[green]✅ 转录成功![/green]")
        rprint(f"   服务器版本: {result.get('server_version', 'unknown')}")
        rprint(f"   语言: {result.get('language', 'unknown')}")
        rprint(f"   处理时间: {result.get('processing_time', 0):.2f}s")
        rprint(f"   段落数: {len(result.get('segments', []))}")
        
        # 保存结果
        output_file = OUTPUT_DIR / 'transcription_result_simple.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        rprint(f"   结果已保存: {output_file}")
        
        # 显示部分转录结果
        segments = result.get('segments', [])
        if segments:
            rprint(f"\n[cyan]前 3 个段落示例:[/cyan]")
            for i, seg in enumerate(segments[:3], 1):
                text = seg.get('text', '')
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                rprint(f"   {i}. [{start:.2f}s - {end:.2f}s] {text}")
        
        return True, result
        
    except Exception as e:
        rprint(f"[red]❌ 转录失败:[/red] {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_transcribe_with_api_function():
    """使用项目集成函数测试 - transcribe_audio_cloud"""
    rprint("\n[bold cyan]=== 4. 集成函数测试 (使用 transcribe_audio_cloud) ===[/bold cyan]\n")
    
    # 转换视频为音频
    audio_file = OUTPUT_DIR / 'test_audio.mp3'
    vocal_audio_file = OUTPUT_DIR / 'test_audio_vocal.mp3'
    
    if not os.path.exists(audio_file):
        convert_video_to_audio(VIDEO_FILE, str(audio_file))
    
    # 复制一份作为 vocal_audio（实际项目中会进行人声分离）
    if not os.path.exists(vocal_audio_file):
        import shutil
        shutil.copy(audio_file, vocal_audio_file)
    
    # 获取音频时长
    from whisperx_cloud.whisperx_cloud_client import WhisperXCloudClient
    client = WhisperXCloudClient(CLOUD_URL)
    
    # 转录前 60 秒（测试）
    start_time = 0.0
    end_time = 60.0
    
    rprint(f"[blue]🎯 转录片段:[/blue] {start_time:.2f}s - {end_time:.2f}s")
    
    try:
        result = transcribe_audio_cloud(
            raw_audio_file=str(audio_file),
            vocal_audio_file=str(vocal_audio_file),
            start=start_time,
            end=end_time,
            cloud_url=CLOUD_URL,
            language=None,
            model='large-v3',
            align=True,
            speaker_diarization=False,
            timeout=600
        )
        
        rprint("\n[green]✅ 转录成功![/green]")
        rprint(f"   服务器版本: {result.get('server_version', 'unknown')}")
        rprint(f"   语言: {result.get('language', 'unknown')}")
        rprint(f"   段落数: {len(result.get('segments', []))}")
        
        # 保存结果
        output_file = OUTPUT_DIR / 'transcription_result_api.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        rprint(f"   结果已保存: {output_file}")
        
        # 显示转录结果
        segments = result.get('segments', [])
        if segments:
            rprint(f"\n[cyan]转录段落:[/cyan]")
            for i, seg in enumerate(segments, 1):
                text = seg.get('text', '')
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                rprint(f"   {i}. [{start:.2f}s - {end:.2f}s] {text}")
                
                # 显示词级时间戳（如果有）
                words = seg.get('words', [])
                if words:
                    rprint(f"      词级时间戳:")
                    for word in words[:5]:  # 只显示前5个词
                        w_text = word.get('word', '')
                        w_start = word.get('start', 0)
                        w_end = word.get('end', 0)
                        rprint(f"         [{w_start:.2f}s - {w_end:.2f}s] {w_text}")
                    if len(words) > 5:
                        rprint(f"         ... 还有 {len(words) - 5} 个词")
        
        return True, result
        
    except Exception as e:
        rprint(f"[red]❌ 转录失败:[/red] {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    """主函数"""
    rprint("[bold green]========================================[/bold green]")
    rprint("[bold green]  WhisperX Cloud 服务测试[/bold green]")
    rprint(f"[bold green]  URL: {CLOUD_URL}[/bold green]")
    rprint("[bold green]========================================[/bold green]")
    
    # 运行测试
    tests = [
        ("健康检查", test_health_check),
        ("连接测试", test_connection),
        ("简单转录测试", test_transcribe_simple),
        ("集成函数测试", test_transcribe_with_api_function),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            if isinstance(result, tuple):
                results.append((name, result[0]))
            else:
                results.append((name, result))
        except KeyboardInterrupt:
            rprint("\n[yellow]⚠️ 测试被用户中断[/yellow]")
            break
        except Exception as e:
            rprint(f"\n[red]❌ 测试 '{name}' 发生异常:[/red] {e}")
            results.append((name, False))
    
    # 总结
    rprint("\n[bold cyan]=== 测试总结 ===[/bold cyan]")
    for name, passed in results:
        status = "[green]✅ 通过[/green]" if passed else "[red]❌ 失败[/red]"
        rprint(f"{status} {name}")
    
    rprint(f"\n[blue]📁 输出目录:[/blue] {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
