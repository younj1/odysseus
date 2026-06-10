#!/usr/bin/env python3
"""Entry point for ARIA CLI — run from project root."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aria.cli.main import main
main()
