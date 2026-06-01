#!/usr/bin/env python3
"""Analyze and report on handlers to keep/remove."""

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

# Find all @on('Kind') - need to search since lines may have leading whitespace
pattern = r"@on\('(\w+)'\)"
handler_lines = []
for i, line in enumerate(lines):
    m = re.search(pattern, line)
    if m:
        handler_lines.append((i, m.group(1)))

print(f"Total lines: {len(lines)}")
print(f"Handler decorators found: {len(handler_lines)}")

to_keep = [(ln, kind) for ln, kind in handler_lines if should_keep(kind)]
to_remove = [(ln, kind) for ln, kind in handler_lines if not should_keep(kind)]

print(f"\nTo keep: {len(to_keep)}")
print(f"To remove: {len(to_remove)}")

# Show sample of what we're removing
print("\nSample handlers to remove:")
for ln, kind in sorted(to_remove, key=lambda x: x[1])[:20]:
    print(f"  {kind}")

# Save lists
with open('scripts/handlers_to_keep.txt', 'w') as f:
    for ln, kind in to_keep:
        f.write(f"{ln}: {kind}\n")

with open('scripts/handlers_to_remove.txt', 'w') as f:
    f.write(f"# {len(to_remove)} handlers to remove\n\n")
    for ln, kind in sorted(to_remove, key=lambda x: x[1]):
        f.write(f"{kind}\n")

print(f"\nLists saved:")
print(f"  handlers_to_keep.txt: {len(to_keep)} handlers")
print(f"  handlers_to_remove.txt: {len(to_remove)} handlers")