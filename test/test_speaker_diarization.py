#!/usr/bin/env python3
"""
测试脚本：使用远程云端服务进行4角色说话人识别测试
测试音频：demo/demo-rzdf.mp3 (4个角色说话)
远程服务：https://adiaphoristic-zaire-reminiscently.ngrok-free.dev/
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from videolingo_cloud.unified_client import UnifiedCloudClient, check_cloud_connection
from rich import print as rprint
import json

# 配置
CLOUD_URL = "https://adiaphoristic-zaire-reminiscently.ngrok-free.dev"
TEST_AUDIO = "demo/demo-rzdf.mp3"

# Token 认证
# 可以通过环境变量设置: export CLOUD_TOKEN="your_token"
# 或直接在这里配置
CLOUD_TOKEN = os.getenv("CLOUD_TOKEN", "ac4dbb16-7d3f-4e6a-9a1a-b27672f1aac8")

def test_health_check():
    """测试服务器健康状态"""
    rprint("\n[bold blue]🔍 步骤1: 检查服务器健康状态[/bold blue]")
    result = check_cloud_connection(CLOUD_URL)
    
    if result['available']:
        rprint("[green]✅ 服务器连接成功[/green]")
        rprint(f"[cyan]  平台:[/cyan] {result.get('platform', 'unknown')}")
        rprint(f"[cyan]  设备:[/cyan] {result.get('device', 'unknown')}")
        rprint(f"[cyan]  GPU内存:[/cyan] {result.get('gpu_memory', 'N/A')} GB")
        
        # 检查说话人分离模型是否已加载
        if result.get('diarize_model_loaded'):
            rprint("[green]  ✅ 说话人分离模型已加载[/green]")
        else:
            rprint("[yellow]  ⚠️ 说话人分离模型未加载[/yellow]")
        
        services = result.get('services', {})
        for svc_name, svc_info in services.items():
            status = "✅" if svc_info.get('available') else "❌"
            rprint(f"  {status} {svc_name}: {svc_info.get('endpoint', '')}")
        return True
    else:
        rprint(f"[red]❌ 服务器连接失败: {result.get('error')}[/red]")
        return False

def test_speaker_diarization():
    """测试说话人识别功能"""
    rprint("\n[bold blue]🔍 步骤2: 测试4角色说话人识别[/bold blue]")
    
    if not os.path.exists(TEST_AUDIO):
        rprint(f"[red]❌ 测试音频不存在: {TEST_AUDIO}[/red]")
        return False
    
    rprint(f"[cyan]📁 测试音频:[/cyan] {TEST_AUDIO}")
    file_size = os.path.getsize(TEST_AUDIO) / 1024 / 1024
    rprint(f"[cyan]📊 文件大小:[/cyan] {file_size:.2f} MB")
    
    client = UnifiedCloudClient(base_url=CLOUD_URL, token=CLOUD_TOKEN if CLOUD_TOKEN else None)
    
    # 测试场景1: 启用说话人识别，预期4个说话人
    rprint("\n[bold yellow]测试场景1: 启用说话人识别 (min_speakers=3, max_speakers=5)[/bold yellow]")
    
    try:
        result = client.transcribe(
            audio_path=TEST_AUDIO,
            language="zh",
            model="large-v3",
            align=True,
            speaker_diarization=True,
            timeout=600
        )
        
        if result.get('success'):
            rprint("[green]✅ 转录成功[/green]")
            rprint(f"[cyan]  语言:[/cyan] {result.get('language')}")
            rprint(f"[cyan]  处理时间:[/cyan] {result.get('processing_time', 0):.2f}秒")
            
            # 打印完整响应用于调试
            rprint(f"\n[dim]完整响应 keys: {list(result.keys())}[/dim]")
            
            speakers = result.get('speakers')
            segments = result.get('segments', [])
            
            rprint(f"[cyan]  总片段数:[/cyan] {len(segments)}")
            
            if speakers:
                rprint(f"[cyan]  检测到的说话人数:[/cyan] {len(speakers)}")
                rprint(f"[green]  说话人列表:[/green] {speakers}")
                
                # 统计每个说话人的片段数和字数
                speaker_stats = {}
                for seg in segments:
                    spk = seg.get('speaker', 'UNKNOWN')
                    if spk not in speaker_stats:
                        speaker_stats[spk] = {'segments': 0, 'words': 0, 'duration': 0}
                    speaker_stats[spk]['segments'] += 1
                    speaker_stats[spk]['duration'] += seg.get('end', 0) - seg.get('start', 0)
                    if 'words' in seg:
                        speaker_stats[spk]['words'] += len(seg['words'])
                
                rprint("\n[bold cyan]说话人统计:[/bold cyan]")
                for spk, stats in sorted(speaker_stats.items()):
                    rprint(f"  {spk}: {stats['segments']}个片段, {stats['words']}个词, {stats['duration']:.2f}秒")
                
                # 显示前5个片段示例
                rprint("\n[bold cyan]前5个片段示例:[/bold cyan]")
                for i, seg in enumerate(segments[:5]):
                    spk = seg.get('speaker', 'UNKNOWN')
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    text = seg.get('text', '')[:50]  # 截取前50字符
                    rprint(f"  [{spk}] {start:.2f}s-{end:.2f}s: {text}...")
            else:
                rprint("[yellow]  ⚠️ 未检测到说话人信息[/yellow]")
                rprint("[dim]  可能原因：服务端 HF_TOKEN 未配置，或音频中说话人区分不明显[/dim]")
                
                # 仍然显示片段信息
                rprint("\n[bold cyan]前5个片段示例 (无说话人标记):[/bold cyan]")
                for i, seg in enumerate(segments[:5]):
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    text = seg.get('text', '')[:50]
                    rprint(f"  {start:.2f}s-{end:.2f}s: {text}...")
            
            # 保存完整结果
            output_file = "test/speaker_diarization_result.json"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            rprint(f"\n[green]💾 结果已保存到: {output_file}[/green]")
            
            return True
        else:
            rprint(f"[red]❌ 转录失败: {result}[/red]")
            return False
            
    except Exception as e:
        rprint(f"[red]❌ 测试失败: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False

def test_without_diarization():
    """对比测试：不启用说话人识别"""
    rprint("\n[bold blue]🔍 步骤3: 对比测试 - 不启用说话人识别[/bold blue]")
    
    client = UnifiedCloudClient(base_url=CLOUD_URL, token=CLOUD_TOKEN if CLOUD_TOKEN else None)
    
    try:
        result = client.transcribe(
            audio_path=TEST_AUDIO,
            language="zh",
            model="large-v3",
            align=True,
            speaker_diarization=False,
            timeout=600
        )
        
        if result.get('success'):
            rprint("[green]✅ 转录成功（无说话人识别）[/green]")
            rprint(f"[cyan]  处理时间:[/cyan] {result.get('processing_time', 0):.2f}秒")
            rprint(f"[cyan]  总片段数:[/cyan] {len(result.get('segments', []))}")
            rprint("[dim]  注意: 此结果未包含说话人信息[/dim]")
            return True
        else:
            rprint(f"[red]❌ 转录失败: {result}[/red]")
            return False
            
    except Exception as e:
        rprint(f"[red]❌ 测试失败: {str(e)}[/red]")
        return False

def main():
    """主函数"""
    rprint("[bold green]🚀 VideoLingo 云端说话人识别测试[/bold green]")
    rprint(f"[dim]远程服务: {CLOUD_URL}[/dim]")
    rprint(f"[dim]测试音频: {TEST_AUDIO}[/dim]")
    rprint("=" * 60)
    
    # 检查音频文件
    if not os.path.exists(TEST_AUDIO):
        rprint(f"[red]❌ 错误: 测试音频不存在 {TEST_AUDIO}[/red]")
        sys.exit(1)
    
    # 步骤1: 健康检查
    if not test_health_check():
        rprint("\n[red]❌ 服务器连接失败，测试终止[/red]")
        sys.exit(1)
    
    # 步骤2: 说话人识别测试
    success1 = test_speaker_diarization()
    
    # 步骤3: 对比测试
    success2 = test_without_diarization()
    
    # 总结
    rprint("\n" + "=" * 60)
    rprint("[bold green]📊 测试总结[/bold green]")
    if success1:
        rprint("[green]✅ 说话人识别测试通过[/green]")
    else:
        rprint("[red]❌ 说话人识别测试失败[/red]")
    
    if success2:
        rprint("[green]✅ 普通转录测试通过[/green]")
    else:
        rprint("[red]❌ 普通转录测试失败[/red]")

if __name__ == "__main__":
    main()
