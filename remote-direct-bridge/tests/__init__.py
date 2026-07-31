import os
import sys

# Make the bridge package importable when running tests from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
