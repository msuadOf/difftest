#!/usr/bin/env python3
"""
Unit test for RV64 CSR normalization fix.

This test demonstrates that when isa_width='rv64' is explicitly provided,
the signature checker correctly masks only bit 63 (SD bit in RV64) and
preserves bit 31 differences.

Before the fix:
- The code used value-based detection, which would incorrectly clear bit 31
  for RV64 values like 0x0000000080006000

After the fix:
- When isa_width='rv64' is explicitly set, only bit 63 is masked
- Bit 31 differences are preserved (they will be reported as mismatches)
"""

import sys
import os

# Add paths for imports
fuzzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'difuzz-rtl', 'Fuzzer')
src_path = os.path.join(fuzzer_path, 'src')
sys.path.insert(0, src_path)
sys.path.insert(0, fuzzer_path)

from signature_checker import sigChecker


def test_rv64_csr_normalization():
    """Test that RV64 CSR normalization masks only bit 63."""

    # Create a temporary sigChecker with explicit RV64 width
    checker = sigChecker(None, None, debug=False, minimizing=False, isa_width='rv64')

    # Test case 1: RV64 mstatus with SD bit set (bit 63)
    # ISA has SD bit set, RTL has SD bit clear - should match after normalization
    isa_val = 0x8000000000006000  # RV64 mstatus with SD bit (bit 63) set
    rtl_val = 0x0000000000006000  # RV64 mstatus without SD bit

    normalized_isa, normalized_rtl = checker._normalize_csr_value('mstatus', isa_val, rtl_val)

    assert normalized_isa == normalized_rtl, (
        f"RV64 SD bit normalization failed: "
        f"ISA={isa_val:016x} RTL={rtl_val:016x} -> "
        f"norm_ISA={normalized_isa:016x} norm_RTL={normalized_rtl:016x}"
    )
    print("✓ Test 1 passed: RV64 SD bit (bit 63) correctly masked")

    # Test case 2: RV64 bit 31 difference - should NOT be masked
    # This is the key regression test for the fix
    # Before fix: would incorrectly mask bit 31, causing false match
    # After fix: bit 31 difference is preserved
    isa_val = 0x0000000080006000  # RV64 with bit 31 set
    rtl_val = 0x0000000000006000  # RV64 with bit 31 clear

    normalized_isa, normalized_rtl = checker._normalize_csr_value('mstatus', isa_val, rtl_val)

    assert normalized_isa != normalized_rtl, (
        f"RV64 bit 31 should NOT be masked: "
        f"ISA={isa_val:016x} RTL={rtl_val:016x} -> "
        f"norm_ISA={normalized_isa:016x} norm_RTL={normalized_rtl:016x}"
    )
    assert normalized_isa == 0x0000000080006000, (
        f"RV64 bit 31 should be preserved in ISA value: {normalized_isa:016x}"
    )
    assert normalized_rtl == 0x0000000000006000, (
        f"RV64 bit 31 should be preserved in RTL value: {normalized_rtl:016x}"
    )
    print("✓ Test 2 passed: RV64 bit 31 differences are preserved (will be reported as mismatch)")


def test_rv32_csr_normalization():
    """Test that RV32 CSR normalization masks bit 31."""

    # Create a temporary sigChecker with explicit RV32 width
    checker = sigChecker(None, None, debug=False, minimizing=False, isa_width='rv32')

    # Test case 1: RV32 mstatus with SD bit set (bit 31)
    # ISA has SD bit set, RTL has SD bit clear - should match after normalization
    isa_val = 0x80006000  # RV32 mstatus with SD bit (bit 31) set
    rtl_val = 0x00006000  # RV32 mstatus without SD bit

    normalized_isa, normalized_rtl = checker._normalize_csr_value('mstatus', isa_val, rtl_val)

    assert normalized_isa == normalized_rtl, (
        f"RV32 SD bit normalization failed: "
        f"ISA={isa_val:08x} RTL={rtl_val:08x} -> "
        f"norm_ISA={normalized_isa:08x} norm_RTL={normalized_rtl:08x}"
    )
    print("✓ Test 3 passed: RV32 SD bit (bit 31) correctly masked")


def test_backward_compatibility():
    """Test that value-based detection still works when isa_width is not provided."""

    # Create a sigChecker without explicit isa_width (backward compatibility)
    checker = sigChecker(None, None, debug=False, minimizing=False)

    # Test case: Large value (> 32 bits) should be detected as RV64
    isa_val = 0x8000000000006000  # Clearly RV64 (bit 63 set)
    rtl_val = 0x0000000000006000

    normalized_isa, normalized_rtl = checker._normalize_csr_value('mstatus', isa_val, rtl_val)

    # With value-based detection, this should mask bit 63
    assert normalized_isa == normalized_rtl, (
        f"Value-based RV64 detection failed: "
        f"ISA={isa_val:016x} RTL={rtl_val:016x} -> "
        f"norm_ISA={normalized_isa:016x} norm_RTL={normalized_rtl:016x}"
    )
    print("✓ Test 4 passed: Backward compatibility - value-based detection works")

    # Test case: Small value (<= 32 bits) should be detected as RV32
    isa_val = 0x80006000  # Clearly RV32 (bit 31 set, value fits in 32 bits)
    rtl_val = 0x00006000

    normalized_isa, normalized_rtl = checker._normalize_csr_value('mstatus', isa_val, rtl_val)

    # With value-based detection, this should mask bit 31
    assert normalized_isa == normalized_rtl, (
        f"Value-based RV32 detection failed: "
        f"ISA={isa_val:08x} RTL={rtl_val:08x} -> "
        f"norm_ISA={normalized_isa:08x} norm_RTL={normalized_rtl:08x}"
    )
    print("✓ Test 5 passed: Backward compatibility - value-based detection works for RV32")


def test_rv64_bit31_preservation_key():
    """
    Key regression test from Codex Round 9 review:

    An RV64 pair such as 0x0000000080006000 vs 0x0000000000006000
    should be normalized to preserve the bit-31 difference (mismatch),
    not falsely match by clearing bit 31.

    The bug was that value-based detection sees both values fit in 32 bits
    (bit 63 is clear in both), so it incorrectly uses RV32 mask (0x7FFFFFFF).

    With explicit isa_width='rv64', we use RV64 mask (0x7FFFFFFFFFFFFFFF)
    which only clears bit 63, preserving the bit-31 difference.
    """

    # The problematic case from Codex review
    isa_val = 0x0000000080006000  # RV64: bit 31 set, bit 63 clear
    rtl_val = 0x0000000000006000  # RV64: both bits clear

    # Without explicit width (old buggy behavior)
    checker_old = sigChecker(None, None, debug=False, minimizing=False)
    norm_isa_old, norm_rtl_old = checker_old._normalize_csr_value('mstatus', isa_val, rtl_val)

    # This would incorrectly match because value-based detection sees both < 2^32
    # and uses RV32 mask
    assert norm_isa_old == norm_rtl_old, (
        "Expected: Old code would incorrectly match (this is the bug)"
    )
    print("✓ Test 6a: Confirmed old behavior - value-based detection causes false match for RV64 bit-31 case")

    # With explicit isa_width='rv64' (new correct behavior)
    checker_new = sigChecker(None, None, debug=False, minimizing=False, isa_width='rv64')
    norm_isa_new, norm_rtl_new = checker_new._normalize_csr_value('mstatus', isa_val, rtl_val)

    # This should preserve the difference (mismatch) because we only mask bit 63
    assert norm_isa_new != norm_rtl_new, (
        f"New behavior should preserve bit-31 difference: "
        f"ISA={norm_isa_new:016x} RTL={norm_rtl_new:016x}"
    )
    assert norm_isa_new == 0x0000000080006000, (
        f"ISA bit 31 should be preserved: {norm_isa_new:016x}"
    )
    assert norm_rtl_new == 0x0000000000006000, (
        f"RTL value should be unchanged: {norm_rtl_new:016x}"
    )
    print("✓ Test 6b: New behavior with explicit isa_width='rv64' - bit 31 difference preserved")


if __name__ == '__main__':
    print("Testing RV64 CSR normalization fix...")
    print("=" * 60)

    test_rv64_csr_normalization()
    print()
    test_rv32_csr_normalization()
    print()
    test_backward_compatibility()
    print()
    test_rv64_bit31_preservation_key()

    print("=" * 60)
    print("All tests passed! ✓")
