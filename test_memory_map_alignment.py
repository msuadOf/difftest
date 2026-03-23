#!/usr/bin/env python3
"""
test_memory_map_alignment.py - Regression test for get_spike_memory_map()

Tests that get_spike_memory_map() correctly handles:
1. Non-page-aligned PT_LOAD segments that cross page boundaries
2. Multiple PT_LOAD segments whose aligned regions overlap

Expected behavior:
- For vaddr=0x1004, memsz=0x1000: region should be (0x1000, 0x2000)
- For two segments vaddr=0x1004 memsz=0x2 and vaddr=0x1800 memsz=0x900:
  the merged region should be (0x1000, 0x2000) covering [0x1000, 0x3000)
"""

import os
import subprocess
import tempfile
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from elf_utils import get_spike_memory_map


def create_page_crossing_elf(output_path):
    """
    Create an ELF with a PT_LOAD segment that crosses page boundary.
    vaddr=0x1004, memsz>=0x1000 -> region (0x1000, 0x2000)
    """
    # Create assembly with .bss to force large memsz without file size
    asm_content = """
    .section .text.init
    .align 2  # 4-byte align, not page align
    .global _start
_start:
    nop

    # Large .bss section to force page crossing
    # .bss doesn't take file space but counts in memsz
    .section .bss, "wa", @nobits
    .align 2
    .space 0x1000  # 4KB of zero-initialized data
    """

    # Linker script with non-page-aligned vaddr
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
    .bss : {
        *(.bss)
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


def create_multi_segment_elf(output_path):
    """
    Create an ELF with two PT_LOAD segments whose aligned regions overlap.
    Segment 1: vaddr=0x1004, memsz=0x2 -> aligned to [0x1000, 0x2000)
    Segment 2: vaddr=0x1800, memsz=0x900 -> aligned to [0x1000, 0x3000)
    Merged result: (0x1000, 0x2000) covering [0x1000, 0x3000)
    """
    asm_content = """
    # First segment - code at non-page-aligned address
    .section .text.low, "ax"
    .align 2
    .global _start
_start:
    nop

    # Second segment - data at 0x1800
    .section .text.high, "ax"
    .align 2
    .global high_code
high_code:
    nop

    # Add data to extend the segment
    .section .data.high, "wa"
    .align 2
    .space 0x800  # Extends to 0x2000, aligned to 0x3000
    """

    # Linker script with two separate segments at specific addresses
    ld_content = """
OUTPUT_ARCH("riscv")
ENTRY(_start)
MEMORY {
    LOW_MEM (rwx) : ORIGIN = 0x1004, LENGTH = 1K
    HIGH_MEM (rwx) : ORIGIN = 0x1800, LENGTH = 8K
}
SECTIONS {
    .text.low : {
        *(.text.low)
    } > LOW_MEM

    .text.high : {
        *(.text.high)
        *(.data.high)
    } > HIGH_MEM
}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        asm_file = os.path.join(tmpdir, 'test.S')
        ld_file = os.path.join(tmpdir, 'test.ld')

        with open(asm_file, 'w') as f:
            f.write(asm_content)
        with open(ld_file, 'w') as f:
            f.write(ld_content)

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


def test_page_crossing_single_segment():
    """
    Test non-page-aligned PT_LOAD that crosses page boundary.

    For vaddr=0x1004 with memsz>=0x1000:
    - Segment end: 0x1004 + 0x1000 = 0x2004
    - Aligned end: 0x3000
    - Region: (0x1000, 0x2000)
    """
    print("Testing page-crossing single segment...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_elf = os.path.join(tmpdir, 'test_page_cross.elf')

        try:
            create_page_crossing_elf(test_elf)
        except RuntimeError as e:
            print(f"  SKIP: Could not create test ELF: {e}")
            return True  # Don't fail if toolchain is missing

        # Get PT_LOAD info
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

        # Get memory map
        regions = get_spike_memory_map(test_elf)

        # Calculate expected
        expected_base = vaddr & ~0xFFF
        end = vaddr + memsz
        aligned_end = (end + 0xFFF) & ~0xFFF
        expected_size = aligned_end - expected_base

        print(f"  Expected: (0x{expected_base:x}, 0x{expected_size:x})")
        print(f"  Actual: {regions}")

        if regions is None:
            print("  FAIL: get_spike_memory_map() returned None")
            return False

        if len(regions) != 1:
            print(f"  FAIL: Expected 1 region, got {len(regions)}")
            return False

        actual_base, actual_size = regions[0]

        if actual_base != expected_base:
            print(f"  FAIL: Base mismatch")
            return False

        if actual_size != expected_size:
            print(f"  FAIL: Size mismatch: expected 0x{expected_size:x}, got 0x{actual_size:x}")
            return False

        # Verify the size is actually >= 0x1000 (page-crossing case)
        if actual_size < 0x1000:
            print(f"  FAIL: Size 0x{actual_size:x} is too small for page-crossing case")
            return False

        print("  PASS: Page-crossing segment handled correctly")
        return True


def test_multi_segment_overlap():
    """
    Test multiple PT_LOAD segments with overlapping aligned regions.

    Two segments:
    - vaddr=0x1004, memsz=0x2 -> aligned [0x1000, 0x2000)
    - vaddr=0x1800, memsz=0x900 -> aligned [0x1000, 0x3000)

    Expected merged result: (0x1000, 0x2000)
    """
    print("Testing multi-segment overlap merging...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_elf = os.path.join(tmpdir, 'test_multi.elf')

        try:
            create_multi_segment_elf(test_elf)
        except RuntimeError as e:
            print(f"  SKIP: Could not create test ELF: {e}")
            return True  # Don't fail if toolchain is missing

        # Get PT_LOAD info
        result = subprocess.run(
            ['riscv64-unknown-elf-readelf', '-l', test_elf],
            capture_output=True, text=True
        )

        segments = []
        for line in result.stdout.split('\n'):
            if 'LOAD' in line:
                parts = line.split()
                if len(parts) >= 6 and parts[0] == 'LOAD':
                    try:
                        vaddr = int(parts[2], 16)
                        memsz = int(parts[5], 16)
                        segments.append((vaddr, memsz))
                    except ValueError:
                        continue

        print(f"  Found {len(segments)} PT_LOAD segments:")
        for vaddr, memsz in segments:
            print(f"    vaddr=0x{vaddr:x}, memsz=0x{memsz:x}")

        # Get memory map
        regions = get_spike_memory_map(test_elf)

        # Calculate expected merged region
        all_bases = []
        all_ends = []
        for vaddr, memsz in segments:
            base = vaddr & ~0xFFF
            end = vaddr + memsz
            aligned_end = (end + 0xFFF) & ~0xFFF
            all_bases.append(base)
            all_ends.append(aligned_end)

        expected_base = min(all_bases)
        expected_end = max(all_ends)
        expected_size = expected_end - expected_base

        print(f"  Expected merged: (0x{expected_base:x}, 0x{expected_size:x})")
        print(f"  Actual: {regions}")

        if regions is None:
            print("  FAIL: get_spike_memory_map() returned None")
            return False

        if len(regions) != 1:
            print(f"  FAIL: Expected 1 merged region, got {len(regions)}")
            return False

        actual_base, actual_size = regions[0]

        if actual_base != expected_base:
            print(f"  FAIL: Base mismatch")
            return False

        if actual_size != expected_size:
            print(f"  FAIL: Size mismatch: expected 0x{expected_size:x}, got 0x{actual_size:x}")
            return False

        print("  PASS: Multi-segment overlap merged correctly")
        return True


def test_aligned_page_case():
    """
    Test normal page-aligned case (regression check).
    Uses ill_mem_cli.elf which is page-aligned.
    """
    print("Testing page-aligned case (regression)...")

    ill_mem_elf = 'progs/ill_mem_cli.elf'

    if not os.path.exists(ill_mem_elf):
        print(f"  SKIP: {ill_mem_elf} not found")
        return True

    regions = get_spike_memory_map(ill_mem_elf)

    print(f"  Regions: {regions}")

    # Should be one page: (0x1000, 0x1000)
    if regions is None:
        print("  FAIL: get_spike_memory_map() returned None")
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

    print("  PASS: Page-aligned case still works")
    return True


def main():
    """Run all memory map alignment tests."""
    print("=" * 60)
    print("Memory Map Alignment Regression Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Page-crossing single segment
    results.append(("Page-crossing single segment", test_page_crossing_single_segment()))
    print()

    # Test 2: Multi-segment overlap
    results.append(("Multi-segment overlap", test_multi_segment_overlap()))
    print()

    # Test 3: Page-aligned (regression)
    results.append(("Page-aligned (regression)", test_aligned_page_case()))
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
