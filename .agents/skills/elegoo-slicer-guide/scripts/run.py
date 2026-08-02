#!/usr/bin/env python3
import sys
import os

# Redirect execution to elegoo_slicer_guide.py
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_script = os.path.join(script_dir, "elegoo_slicer_guide.py")

with open(target_script) as f:
    code = compile(f.read(), target_script, 'exec')
    exec(code, {'__name__': '__main__', '__file__': target_script})
