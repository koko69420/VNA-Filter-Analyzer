#!/usr/bin/env python3
"""Root launcher for VNA Filter Analyzer."""

import sys
import os

# Add root directory to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from vna_filter_analyzer.main import main

if __name__ == "__main__":
    main()
