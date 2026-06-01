#!/usr/bin/env python3
"""Remove handlers by rebuilding the file content."""

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
    content = f.read()

# Strategy: Build new content by extracting only the blocks we want to keep
# Use regex to find each complete handler block
# A handler block: starts with @on('Kind') and includes everything until the next @on( or end of file

# Find all @on positions
pattern = r"@on\('(\w+)'\)"
matches = list(re.finditer(pattern, content))

print(f"Found {len(matches)} handlers")

# For each handler, find where it ends
blocks_to_keep = []
for i, m in enumerate(matches):
    kind = m.group(1)
    start = m.start()
    if should_keep(kind):
        # Find end of this block (start of next @on or end)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)
        blocks_to_keep.append((start, end, kind))
        print(f"Keeping: {kind}")
    else:
        print(f"Removing: {kind}")

print(f"\nBlocks to keep: {len(blocks_to_keep)}")

# Rebuild content
new_content = ''.join(content[start:end] for start, end, kind in blocks_to_keep)

# Clean up multiple blank lines
new_content = re.sub(r'\n{3,}', '\n\n', new_content)

with open(handler_file, 'w') as f:
    f.write(new_content)

print(f"New file size: {len(new_content)} chars")
print(f"Removed: {len(content) - len(new_content)} chars")