#!/usr/bin/env python3
"""Remove handler blocks that don't match pyslang SyntaxKind."""

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

def main():
    handler_file = 'src/trace/core/visitors/signal_expression_visitor.py'
    
    with open(handler_file, 'r') as f:
        content = f.read()
    
    print(f"Original size: {len(content)} chars")
    
    # Strategy: Find complete handler blocks using regex that respects structure
    # A handler block: @on('Kind') followed by def method_name(self, node) -> SignalResult: and body
    
    # Find all handler blocks with their full content
    # Pattern: @on('Kind')\n    def method_name(self, node) -> SignalResult:\n        (docstring and body)
    # We need to find the end which is either the next @on or end of class/indent level
    
    # Find all @on('Kind') positions
    decorator_pattern = r"@on\('(\w+)'\)"
    matches = list(re.finditer(decorator_pattern, content))
    print(f"Found {len(matches)} handlers")
    
    # Build list of blocks to keep/remove
    blocks = []
    for i, match in enumerate(matches):
        kind = match.group(1)
        start = match.start()
        # End is start of next @on or end of content
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)
        blocks.append({
            'kind': kind,
            'start': start,
            'end': end,
            'content': content[start:end],
            'keep': should_keep(kind)
        })
    
    keep_blocks = [b for b in blocks if b['keep']]
    remove_blocks = [b for b in blocks if not b['keep']]
    
    print(f"To keep: {len(keep_blocks)}")
    print(f"To remove: {len(remove_blocks)}")
    
    # Write removed handlers list
    with open('scripts/removed_handlers.txt', 'w') as f:
        f.write(f"# Removed {len(remove_blocks)} handlers\n\n")
        for b in sorted(remove_blocks, key=lambda x: x['kind']):
            f.write(f"{b['kind']}\n")
    
    # Build new content from kept blocks
    new_content = ''.join(b['content'] for b in blocks if b['keep'])
    
    # Clean up multiple blank lines (max 2 consecutive)
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)
    
    with open(handler_file, 'w') as f:
        f.write(new_content)
    
    print(f"New size: {len(new_content)} chars")
    print(f"Removed {len(content) - len(new_content)} chars")
    print(f"Removed handlers list: scripts/removed_handlers.txt")

if __name__ == '__main__':
    main()