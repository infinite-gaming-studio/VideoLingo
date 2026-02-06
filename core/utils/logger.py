import time
from rich.console import Console
from core.utils.config_utils import load_key

# Create a global console instance with timestamps enabled by default
# VideoLingo conventionally uses a prefix for different services
console = Console(log_time=True, log_path=False)

def log_api_call(service: str, method: str, params: dict, response: any, duration: float):
    """Log detailed API call information if debug mode is enabled."""
    if load_key("debug", False):
        console.log(f"[bold cyan]API DEBUG - {service}[/bold cyan]")
        console.log(f"  [yellow]Method:[/yellow] {method}")
        console.log(f"  [yellow]Duration:[/yellow] {duration:.2f}s")
        console.log(f"  [yellow]Params:[/yellow] {params}")
        console.log(f"  [yellow]Response:[/yellow] {response}")

def vprint(*args, **kwargs):
    """
    VideoLingo print: A wrapper around console.log to provide timestamped output.
    Equivalent to rich.print but with timestamps.
    """
    # Join args into a single string for console.log if they are not already
    if args:
        # Check if first arg is a style string (VideoLingo often uses rich's style tags)
        console.log(*args, **kwargs)
    else:
        console.log("", **kwargs)
