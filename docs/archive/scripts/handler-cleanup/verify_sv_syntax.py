#!/usr/bin/env python3
"""Verify all SV RTL in test files using Verilator and Verible"""
import subprocess
import re
import sys
import os
import tempfile
import glob
import argparse

VERILATOR_BIN = "verilator"
VERIBLE_BIN = os.path.expanduser("~/my_daily_proj/verible-v0.0-4053-g89d4d98a-macOS/bin/verible-verilog-lint")

def verify_verilator(source):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
        f.write(source)
        f.flush()
        tmp = f.name
    try:
        result = subprocess.run(
            [VERILATOR_BIN, "--lint-only", "-sv", tmp],
            capture_output=True, text=True, timeout=30
        )
        errors = [l for l in result.stderr.split('\n') if '%Error' in l]
        return len(errors) == 0, errors
    finally:
        os.unlink(tmp)

def verify_verible(source):
    if not os.path.exists(VERIBLE_BIN):
        return True, []  # Skip if not installed
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
        f.write(source)
        f.flush()
        tmp = f.name
    try:
        result = subprocess.run(
            [VERIBLE_BIN, tmp],
            capture_output=True, text=True, timeout=30
        )
        output = result.stderr + result.stdout
        errors = [l for l in output.split('\n') if re.search(r'syntax error', l, re.IGNORECASE)]
        return len(errors) == 0, errors
    finally:
        os.unlink(tmp)

def extract_rtl_from_file(filepath):
    with open(filepath) as f:
        content = f.read()
    blocks = []
    pattern = r'source\s*=\s*["\'\'"]+(.+?)["\'\'"]+'
    matches = re.findall(pattern, content, re.DOTALL)
    for match in matches:
        rtl = match.strip()
        if 'module' in rtl and 'endmodule' in rtl:
            blocks.append(rtl)
    return blocks

def main():
    parser = argparse.ArgumentParser(description='Verify SV syntax')
    parser.add_argument('files', nargs='*', help='Test files to verify')
    parser.add_argument('--verilator-only', action='store_true', help='Only verify with Verilator')
    parser.add_argument('--verible-only', action='store_true', help='Only verify with Verible')
    args = parser.parse_args()
    
    if args.files:
        test_files = args.files
    else:
        test_dir = os.path.join(os.path.dirname(__file__), '..', 'sim', 'tests', 'integration')
        test_dir = os.path.abspath(test_dir)
        test_files = glob.glob(f"{test_dir}/test_*.py")
    
    results = []
    for test_file in sorted(test_files):
        if not os.path.isfile(test_file):
            continue
        blocks = extract_rtl_from_file(test_file)
        for i, rtl in enumerate(blocks):
            v_ok, v_errors = True, [] if args.verilator_only else verify_verible(rtl)
            e_ok, e_errors = True, [] if args.verible_only else verify_verilator(rtl)
            results.append((os.path.basename(test_file), i, v_ok, e_ok, v_errors, e_errors))
    
    v_pass = sum(1 for r in results if r[2])
    v_fail = sum(1 for r in results if not r[2])
    e_pass = sum(1 for r in results if r[3])
    e_fail = sum(1 for r in results if not r[3])
    both_pass = sum(1 for r in results if r[2] and r[3])
    both_fail = sum(1 for r in results if not r[2] and not r[3])
    
    print(f"=== SV Syntax Verification ===")
    print(f"Total RTL blocks: {len(results)}")
    print(f"")
    if not args.verible_only:
        print(f"Verilator: {e_pass} pass, {e_fail} fail")
    if not args.verilator_only:
        print(f"Verible:   {v_pass} pass, {v_fail} fail")
    print(f"Both pass: {both_pass}")
    print(f"Both fail: {both_fail}")
    
    if both_fail > 0 and not args.verilator_only and not args.verible_only:
        print(f"\n=== Failed blocks ===")
        for fname, i, v_ok, e_ok, v_err, e_err in results:
            if not v_ok and not e_ok:
                print(f"\n{fname} block {i}:")
                for e in v_err[:1]:
                    print(f"  Verible: {e[:100]}")
                for e in e_err[:1]:
                    print(f"  Verilator: {e[:100]}")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
