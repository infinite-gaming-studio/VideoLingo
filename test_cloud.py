#!/usr/bin/env python3
"""
Run cloud server tests from test directory
"""

import sys
import os
from pathlib import Path

# Add test directory to path
test_dir = Path(__file__).parent / "test"
sys.path.insert(0, str(test_dir))

# Import and run the test
if __name__ == "__main__":
    os.chdir(test_dir)
    from test_cloud_server import main
    main()
