"""
Root conftest.py — ensures the project root is on sys.path
so that `from src.xxx import ...` works in all test files.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
