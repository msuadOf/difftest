#!/usr/bin/env python3
"""
test_memory_map_alignment.py - Regression test for get_spike_memory_map()

Tests that get_spike_memory_map() correctly handles non-page-aligned PT_LOAD
segments by calculating region size as align_up(vaddr + memsz) - align_down(vaddr).

Example: For vaddr=0x1004, memsz=0x1000:
- Segment end: 0x1004 + 0x1000 = 0x2004
- Aligned end: 0x3000
- Aligned base: 0x1000
- Region size: 0x3000 - 0x1000 = 0x2000
"""

import os
import subprocess
import tempfile
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from elf_utils import get_spike_memory_map


def create_synthetic_elf_with_unaligned_load(output_path):
    """
    Create a synthetic ELF with a non-page-aligned PT_LOAD segment.

    Uses GCC to compile a minimal assembly file that will have
    vaddr=0x1004 (non-page-aligned).
    """
    # Create minimal assembly that forces non-page-aligned layout
    asm_content = """
    .section .text.init
    .align 2  # Only 4-byte align, not page align
    .global _start
_start:
    nop

    # Force some data to extend the segment
    .section .data
    .align 2
    .data_word: .word 0x12345678
    """

    # Create a linker script that forces non-page-aligned vaddr
    ld_content = """
OUTPUT_ARCH("riscv")
ENTRY(_start)
MEMORY {
    LOW_MEM (rwx) : ORIGIN = 0x1004, LENGTH = 128K
}
SECTIONS {
    .text.init : {
        *(.text.init)
    } > LOW_MEM
    .data : {
        *(.data)
    } > LOW_MEM
}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        asm_file = os.path.join(tmpdir, 'test.S')
        ld_file = os.path.join(tmpdir, 'test.ld')

        with open(asm_file, 'w') as f:
            f.write(asm_content)
        with open(ld_file, 'w') as f:
            f.write(ld_content)

        # Compile the ELF
        gcc_cmd = [
            'riscv64-unknown-elf-gcc',
            '-mcmodel=medany',
            '-march=rv32imafdc',
            '-mabi=ilp32d',
            '-nostdlib',
            '-nostartfiles',
            '-T', ld_file,
            asm_file,
            '-o', output_path
        ]

        result = subprocess.run(gcc_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create test ELF: {result.stderr}")


def test_unaligned_pt_load():
    """
    Test that get_spike_memory_map() correctly handles unaligned PT_LOAD segments.

    Expected behavior:
    - PT_LOAD with vaddr=0x1004 should produce region (0x1000, 0x2000)
    - Region base is page-aligned down from vaddr
    - Region size covers from aligned base to aligned end of segment
    """
    print("Testing get_spike_memory_map() with non-page-aligned PT_LOAD...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_elf = os.path.join(tmpdir, 'test_unaligned.elf')

        try:
            create_synthetic_elf_with_unaligned_load(test_elf)
        except RuntimeError as e:
            print(f"  SKIP: Could not create test ELF: {e}")
            print("  This test requires riscv64-unknown-elf-gcc")
            return True  # Don't fail the test suite if toolchain is missing

        # Get memory map
        regions = get_spike_memory_map(test_elf)

        # Check PT_LOAD segments to understand what we're working with
        result = subprocess.run(
            ['riscv64-unknown-elf-readelf', '-l', test_elf],
            capture_output=True, text=True
        )

        vaddr = None
        memsz = None
        for line in result.stdout.split('\n'):
            if 'LOAD' in line:
                parts = line.split()
                if len(parts) >= 6 and parts[0] == 'LOAD':
                    try:
                        vaddr = int(parts[2], 16)
                        memsz = int(parts[5], 16)
                    except ValueError:
                        continue

        print(f"  PT_LOAD: vaddr=0x{vaddr:x}, memsz=0x{memsz:x}")

        # Calculate expected values
        expected_base = vaddr & ~0xFFF  # align_down(vaddr)
        end = vaddr + memsz
        aligned_end = (end + 0xFFF) & ~0xFFF  # align_up(end)
        expected_size = aligned_end - expected_base

        print(f"  Expected region: base=0x{expected_base:x}, size=0x{expected_size:x}")
        print(f"  Actual regions: {regions}")

        # Verify the result
        if regions is None:
            print("  FAIL: get_spike_memory_map() returned None for low-address ELF")
            return False

        if len(regions) != 1:
            print(f"  FAIL: Expected 1 region, got {len(regions)}")
            return False

        actual_base, actual_size = regions[0]

        if actual_base != expected_base:
            print(f"  FAIL: Base mismatch: expected 0x{expected_base:x}, got 0x{actual_base:x}")
            return False

        if actual_size != expected_size:
            print(f"  FAIL: Size mismatch: expected 0x{expected_size:x}, got 0x{actual_size:x}")
            return False

        print("  PASS: Region correctly calculated for unaligned PT_LOAD")
        return True


def test_aligned_pt_load():
    """
    Test that get_spike_memory_map() still works correctly for aligned PT_LOAD.

    This is a regression test to ensure the fix doesn't break normal cases.
    """
    print("Testing get_spike_memory_map() with page-aligned PT_LOAD...")

    # Use the existing ill_mem_cli.elf which is page-aligned
    ill_mem_elf = 'progs/ill_mem_cli.elf'

    if not os.path.exists(ill_mem_elf):
        print(f"  SKIP: {ill_mem_elf} not found")
        return True

    regions = get_spike_memory_map(ill_mem_elf)

    print(f"  Regions: {regions}")

    # Should return a region covering 0x1000-0x2000 (one page)
    if regions is None:
        print("  FAIL: get_spike_memory_map() returned None for ill_mem_cli.elf")
        return False

    if len(regions) != 1:
        print(f"  FAIL: Expected 1 region, got {len(regions)}")
        return False

    base, size = regions[0]

    if base != 0x1000:
        print(f"  FAIL: Expected base 0x1000, got 0x{base:x}")
        return False

    if size != 0x1000:
        print(f"  FAIL: Expected size 0x1000, got 0x{size:x}")
        return False

    print("  PASS: Page-aligned PT_LOAD handled correctly")
    return True


def main():
    """Run all memory map alignment tests."""
    print("=" * 60)
    print("Memory Map Alignment Regression Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Non-page-aligned PT_LOAD
    results.append(("Non-page-aligned PT_LOAD", test_unaligned_pt_load()))
    print()

    # Test 2: Page-aligned PT_LOAD (regression check)
    results.append(("Page-aligned PT_LOAD", test_aligned_pt_load()))
    print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")

    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
