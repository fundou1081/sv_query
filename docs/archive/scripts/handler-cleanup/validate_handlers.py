#!/usr/bin/env python3
"""
Validate pyslang SyntaxKind to Handler Mapping

This script:
1. Loads pyslang SyntaxKind enum values  
2. Extracts all @on handlers from signal_expression_visitor.py
3. Compares them and reports missing/extra handlers
4. Handles Expr<->Expression, Stmt<->Statement suffixes
"""

import re
import sys
import os

sys.path.insert(0, os.path.expanduser('~/miniconda3/lib/python3.11/site-packages'))
from pyslang import SyntaxKind

def get_pyslang_kinds():
    """Get all SyntaxKind values that represent AST node types."""
    kinds = []
    for attr in dir(SyntaxKind):
        if attr.startswith('_'):
            continue
        val = getattr(SyntaxKind, attr)
        if isinstance(val, SyntaxKind):
            kinds.append(attr)
    return sorted(kinds)

def get_handlers():
    """Extract all @on handlers from signal_expression_visitor.py."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..')
    handler_file = os.path.join(project_root, 'src/trace/core/visitors/signal_expression_visitor.py')
    
    with open(handler_file, 'r') as f:
        content = f.read()
    
    pattern = r"@on\('(\w+)'\)"
    matches = re.findall(pattern, content)
    return sorted(set(matches))

def get_variants(name):
    """Generate all possible variants of a name for matching."""
    variants = {name}
    
    # Expr <-> Expression
    if name.endswith('Expr'):
        variants.add(name[:-3] + 'Expression')
    elif name.endswith('Expression'):
        variants.add(name[:-10] + 'Expr')
    
    # Stmt <-> Statement
    if name.endswith('Stmt'):
        variants.add(name[:-4] + 'Statement')
        variants.add(name[:-4] + 'Statement')  # also try just removing Stmt
    elif name.endswith('Statement'):
        variants.add(name[:-8] + 'Stmt')
        variants.add(name[:-8] + 'Statement')  # keep as is
    
    return variants

def main():
    print("=" * 70)
    print("Pyslang SyntaxKind to Handler Validation")
    print("=" * 70)
    
    pyslang_kinds = get_pyslang_kinds()
    print(f"\nTotal pyslang SyntaxKind values: {len(pyslang_kinds)}")
    
    handlers = get_handlers()
    print(f"Total handlers: {len(handlers)}")
    
    pyslang_set = set(pyslang_kinds)
    handler_set = set(handlers)
    
    # Direct matches
    direct_matches = pyslang_set & handler_set
    print(f"\nDirect matches (exact same name): {len(direct_matches)}")
    
    # Find missing: SyntaxKinds that have no matching handler
    missing = []
    for kind in pyslang_kinds:
        variants = get_variants(kind)
        if not (variants & handler_set):
            missing.append(kind)
    
    # Find extra: handlers that don't match any SyntaxKind
    extra = []
    for h in handlers:
        variants = get_variants(h)
        if not (variants & pyslang_set):
            extra.append(h)
    
    # Find covered: handlers that match some SyntaxKind
    covered = []
    for h in handlers:
        variants = get_variants(h)
        if variants & pyslang_set:
            covered.append(h)
    
    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    print(f"\n✓ Total SyntaxKind values: {len(pyslang_kinds)}")
    print(f"✓ Total handlers: {len(handlers)}")
    print(f"✓ Covered (handler matches some SyntaxKind): {len(covered)}")
    print(f"✗ Missing (SyntaxKind has no matching handler): {len(missing)}")
    print(f"? Extra (handler doesn't match any SyntaxKind): {len(extra)}")
    
    coverage = len(covered) / len(handlers) * 100 if handlers else 0
    print(f"\nCoverage: {coverage:.1f}%")
    
    if missing:
        print(f"\n{'=' * 70}")
        print(f"MISSING HANDLERS ({len(missing)} items - SyntaxKind has no handler):")
        print(f"{'=' * 70}")
        for kind in sorted(missing):
            print(f"  @on('{kind}')")
    
    if extra:
        print(f"\n{'=' * 70}")
        print(f"EXTRA HANDLERS ({len(extra)} items - no matching SyntaxKind):")
        print(f"{'=' * 70}")
        # Show first 50
        for h in sorted(extra)[:50]:
            print(f"  {h}")
        if len(extra) > 50:
            print(f"  ... and {len(extra) - 50} more")
    
    # Write report
    report_file = os.path.join(os.path.dirname(__file__), 'HANDLER_VALIDATION_REPORT.md')
    with open(report_file, 'w') as f:
        f.write("# Handler Validation Report\n\n")
        f.write(f"Generated from pyslang\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total pyslang SyntaxKind: {len(pyslang_kinds)}\n")
        f.write(f"- Total handlers: {len(handlers)}\n")
        f.write(f"- Covered: {len(covered)}\n")
        f.write(f"- Missing (SyntaxKind → no handler): {len(missing)}\n")
        f.write(f"- Extra (handler → no SyntaxKind): {len(extra)}\n")
        f.write(f"- Coverage: {coverage:.1f}%\n\n")
        
        f.write("## Missing Handlers\n\n")
        f.write("These SyntaxKind values don't have corresponding handlers:\n\n")
        for kind in sorted(missing):
            f.write(f"- `@on('{kind}')`\n")
        f.write("\n")
        
        f.write("## Extra Handlers\n\n")
        f.write("These handlers don't match any SyntaxKind:\n\n")
        for h in sorted(extra):
            f.write(f"- `{h}`\n")
    
    print(f"\nReport written to: {report_file}")
    
    return 0 if not missing else 1

if __name__ == '__main__':
    sys.exit(main())