#!/usr/bin/env python3
"""Remove handlers by extracting header + valid blocks only."""

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

# Find the first @on decorator - that's where the handlers start
first_on_match = re.search(r"@on\('(\w+)'\)", content)
if not first_on_match:
    print("ERROR: No @on decorators found!")
    sys.exit(1)

header_end = first_on_match.start()
header = content[:header_end]

print(f"Header size: {len(header)} chars")

# Find all @on positions
pattern = r"@on\('(\w+)'\)"
matches = list(re.finditer(pattern, content))

print(f"Found {len(matches)} handlers")

# Get the blocks we want to keep
blocks = []
for i, m in enumerate(matches):
    kind = m.group(1)
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
    
    if should_keep(kind):
        blocks.append((start, end, kind))

print(f"Blocks to keep: {len(blocks)}")

# Rebuild: header + kept blocks
kept_parts = [content[start:end] for start, end, kind in blocks]
new_content = header + ''.join(kept_parts)

# Clean up multiple blank lines (max 2 consecutive)
new_content = re.sub(r'\n{3,}', '\n\n', new_content)

with open(handler_file, 'w') as f:
    f.write(new_content)

print(f"Original size: {len(content)} chars")
print(f"New size: {len(new_content)} chars")
print(f"Removed: {len(content) - len(new_content)} chars")

# Verify it compiles
import py_compile
try:
    py_compile.compile(handler_file, doraise=True)
    print("✓ File compiles successfully!")
except py_compile.PyCompileError as e:
    print(f"✗ Compile error: {e}")