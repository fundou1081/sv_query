#!/usr/bin/env python3
"""Remove extra handlers by carefully rebuilding file."""

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

# Find all handler blocks: @on('Kind') followed by def extract_ or def handle_
pattern = re.compile(r"@on\('(\w+)'\)")
handler_line_nums = []
for i, line in enumerate(lines):
    m = pattern.search(line)
    if m and i + 1 < len(lines):
        next_line = lines[i + 1]
        if 'def extract_' in next_line or 'def handle_' in next_line:
            handler_line_nums.append((i, m.group(1)))

print(f"Found {len(handler_line_nums)} handler blocks")

# Determine which to keep
to_keep = [(ln, kind) for ln, kind in handler_line_nums if should_keep(kind)]
to_remove = [(ln, kind) for ln, kind in handler_line_nums if not should_keep(kind)]

print(f"To keep: {len(to_keep)}")
print(f"To remove: {len(to_remove)}")

# Build set of line numbers to remove
# For each handler to remove, remove from @on line until next handler (or blank lines after)
lines_to_remove = set()
for idx, (start_ln, kind) in enumerate(to_remove):
    lines_to_remove.add(start_ln)
    # Find end of this handler block
    if idx + 1 < len(handler_line_nums):
        next_start_ln = handler_line_nums[idx + 1][0]
    else:
        next_start_ln = len(lines)
    # Remove all lines from start_ln+1 up to next handler
    for i in range(start_ln + 1, next_start_ln):
        lines_to_remove.add(i)

print(f"Lines to remove: {len(lines_to_remove)}")

# Write new file
new_lines = [lines[i] for i in range(len(lines)) if i not in lines_to_remove]

# Clean up blank lines (max 2 consecutive)
cleaned = []
prev_blank = False
blank_count = 0
for line in new_lines:
    is_blank = line.strip() == ''
    if is_blank:
        blank_count += 1
        if blank_count <= 2:
            cleaned.append(line)
    else:
        blank_count = 0
        cleaned.append(line)

new_content = ''.join(cleaned)

with open(handler_file, 'w') as f:
    f.write(new_content)

print(f"New file: {len(new_content)} chars")

# Verify
import py_compile
try:
    py_compile.compile(handler_file, doraise=True)
    print("✓ File compiles successfully!")
except py_compile.PyCompileError as e:
    print(f"✗ Compile error: {e}")
    
    # Restore from git
    os.system('git checkout src/trace/core/visitors/signal_expression_visitor.py')