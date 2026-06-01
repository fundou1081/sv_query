#!/usr/bin/env python3
"""Carefully rebuild file by removing handlers that don't match pyslang."""

import re
import os
import sys

sys.path.insert(0, '/Users/fundou/miniconda3/lib/python3.11/site-packages')
from pyslang import SyntaxKind

# Get all SyntaxKind values
pyslang_kinds = []
for attr in dir(SyntaxKind):
    if attr.startswith('_'):
        continue
    val = getattr(SyntaxKind, attr)
    if isinstance(val, SyntaxKind):
        pyslang_kinds.append(attr)
pyslang_set = set(pyslang_kinds)

def get_variants(name):
    variants = {name}
    if name.endswith('Expr'):
        variants.add(name[:-3] + 'Expression')
    elif name.endswith('Expression'):
        variants.add(name[:-10] + 'Expr')
    if name.endswith('Stmt'):
        variants.add(name[:-4] + 'Statement')
    elif name.endswith('Statement'):
        variants.add(name[:-8] + 'Stmt')
    return variants

def should_keep(kind):
    variants = get_variants(kind)
    return bool(variants & pyslang_set)

handler_file = 'src/trace/core/visitors/signal_expression_visitor.py'
with open(handler_file, 'r') as f:
    lines = f.readlines()

result_lines = []
i = 0
n = len(lines)
removed_count = 0
kept_count = 0

while i < n:
    line = lines[i]
    
    # Check if this is a handler decorator
    m = re.match(r"@on\('(\w+)'\)", line)
    if m and i + 1 < n:
        next_line = lines[i + 1]
        if 'def extract_' in next_line or 'def handle_' in next_line:
            kind = m.group(1)
            if should_keep(kind):
                # Keep this handler block
                block_lines = []
                block_lines.append(line)
                i += 1
                while i < n:
                    next_line = lines[i]
                    if re.match(r"@on\('(\w+)'\)", next_line) and i + 1 < n and ('def extract_' in lines[i + 1] or 'def handle_' in lines[i + 1]):
                        # Next handler starts
                        break
                    block_lines.append(next_line)
                    i += 1
                result_lines.extend(block_lines)
                kept_count += 1
            else:
                # Skip this handler block
                removed_count += 1
                i += 1
                while i < n:
                    next_line = lines[i]
                    if re.match(r"@on\('(\w+)'\)", next_line) and i + 1 < n and ('def extract_' in lines[i + 1] or 'def handle_' in lines[i + 1]):
                        # Next handler starts
                        break
                    i += 1
                if i >= n:
                    break
        else:
            result_lines.append(line)
            i += 1
    else:
        result_lines.append(line)
        i += 1

new_content = '\n'.join(result_lines)

with open(handler_file, 'w') as f:
    f.write(new_content)

print(f"Removed: {removed_count}")
print(f"Kept: {kept_count}")
print(f"New file: {len(new_content)} chars")

# Verify
import py_compile
try:
    py_compile.compile(handler_file, doraise=True)
    print("✓ File compiles successfully!")
except py_compile.PyCompileError as e:
    print(f"✗ Compile error: {e}")
    os.system('git checkout src/trace/core/visitors/signal_expression_visitor.py')