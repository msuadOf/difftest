#!/usr/bin/env python3
"""
Fix cocotb 2.0 API compatibility issues in Python files.

This script updates Python files to use modern cocotb API:
1. Replaces 'from cocotb.decorators import coroutine' with compatibility layer
2. Converts @coroutine decorated functions to async def
3. Replaces 'yield' with 'await' for cocotb triggers
4. Replaces 'cocotb.fork()' with compatibility wrapper
"""

import re
import sys

def fix_cocotb_imports(content):
    """Replace cocotb.decorators.coroutine import with compatibility layer."""
    # Check if the file uses coroutine
    if 'from cocotb.decorators import coroutine' not in content:
        return content, False

    # Check if compatibility layer already exists
    if 'HAS_OLD_COROUTINE' in content:
        return content, False

    # Replace the import line with compatibility layer
    old_import = 'from cocotb.decorators import coroutine'
    new_import = '''# Compatibility layer for different cocotb versions
try:
    from cocotb.decorators import coroutine
    HAS_OLD_COROUTINE = True
except ImportError:
    # cocotb 2.0+ removed @coroutine decorator
    # Define a no-op decorator for async functions
    def coroutine(func):
        """No-op decorator for modern cocotb async functions."""
        return func
    HAS_OLD_COROUTINE = False'''

    content = content.replace(old_import, new_import)

    # Add cocotb_start wrapper after imports
    # Find the last import line
    lines = content.split('\n')
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('from ') or line.strip().startswith('import '):
            last_import_idx = i

    # Insert cocotb_start wrapper after last import
    wrapper_code = '''
# Compatibility for cocotb.fork() vs cocotb.start_soon()
def cocotb_start(func):
    """Compatibility wrapper for starting coroutines across cocotb versions."""
    try:
        return cocotb.start_soon(func)
    except AttributeError:
        # cocotb < 2.0
        return cocotb.fork(func)
'''
    lines.insert(last_import_idx + 1, wrapper_code)
    content = '\n'.join(lines)

    return content, True

def fix_coroutine_to_async(content):
    """Convert @coroutine decorated functions to async def."""
    # Find all @coroutine patterns
    pattern = r'(\s+)@coroutine\s*\n\s+def\s+(\w+)\s*\('

    def replace_func(match):
        indent = match.group(1)
        func_name = match.group(2)
        return f'{indent}async def {func_name}('

    content = re.sub(pattern, replace_func, content)
    return content

def fix_yield_to_await(content):
    """Replace 'yield' with 'await' for cocotb triggers."""
    # This is a simplified conversion - only replace yield with await
    # for trigger patterns (RisingEdge, Timer, etc.)
    patterns = [
        (r'yield\s+(RisingEdge\([^)]+\))', r'await \1'),
        (r'yield\s+(Timer\([^)]+\))', r'await \1'),
        (r'yield\s+(clkedge)', r'await clkedge'),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    return content

def fix_cocotb_fork(content):
    """Replace cocotb.fork() with cocotb_start() wrapper."""
    # Replace cocotb.fork(...) with cocotb_start(...)
    content = re.sub(r'cocotb\.fork\(', 'cocotb_start(', content)
    return content

def fix_file(filepath):
    """Fix a single Python file."""
    print(f"Fixing {filepath}...")

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    modified = False

    # Step 1: Fix imports
    content, imports_modified = fix_cocotb_imports(content)
    if imports_modified:
        modified = True
        print(f"  - Fixed cocotb.decorators.coroutine import")

    # Step 2: Convert @coroutine to async def
    new_content = fix_coroutine_to_async(content)
    if new_content != content:
        modified = True
        print(f"  - Converted @coroutine to async def")
    content = new_content

    # Step 3: Replace yield with await
    new_content = fix_yield_to_await(content)
    if new_content != content:
        modified = True
        print(f"  - Replaced yield with await")
    content = new_content

    # Step 4: Replace cocotb.fork with cocotb_start
    new_content = fix_cocotb_fork(content)
    if new_content != content:
        modified = True
        print(f"  - Replaced cocotb.fork with cocotb_start")
    content = new_content

    if modified:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ Fixed {filepath}")
        return True
    else:
        print(f"  - No changes needed for {filepath}")
        return False

if __name__ == '__main__':
    files = [
        'difuzz-rtl/Fuzzer/src/multicore_manager.py',
        'difuzz-rtl/Fuzzer/RTLSim/src/adapters/tilelink/adapter.py',
        'difuzz-rtl/Fuzzer/Fuzzer.py',
        'difuzz-rtl/Fuzzer/Minimizer.py',
    ]

    for filepath in files:
        try:
            fix_file(filepath)
        except Exception as e:
            print(f"  ✗ Error fixing {filepath}: {e}")

    print("\nDone!")
