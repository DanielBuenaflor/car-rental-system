#!/usr/bin/env python3
"""Fix curly/smart quotes in user_bp.py that cause Python syntax errors"""

import os

filepath = r"C:\Users\Admin\Desktop\car\car-rental-system\MyFlaskApp\user\user_bp.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace curly quotes with straight quotes
replacements = {
    '\u2018': "'",   # left single quotation mark
    '\u2019': "'",   # right single quotation mark  
    '\u201c': '"',   # left double quotation mark
    '\u201d': '"',   # right double quotation mark
}

for curly, straight in replacements.items():
    content = content.replace(curly, straight)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed curly quotes in user_bp.py")
