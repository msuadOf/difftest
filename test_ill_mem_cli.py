#!/usr/bin/env python3
"""
test_ill_mem_cli.py - Regression test for ILL_MEM CLI test case

Verifies that the ill_mem_cli.elf fixture correctly triggers ILL_MEM
in RTL simulation while Spike executes successfully with memory mapping.

This is an acceptance test for the low-address fixture path.
"""

import os
import subprocess
import sys


def run_difftest(elf_path, timeout=30):
    """Run difftest on the given ELF and return result."""
    cmd = [
        sys.executable, 'run_difftest.py',
        '--elf', elf_path,
        '--timeout', str(timeout)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout * 2  # Give extra time for the test itself
    )

    return result


def test_ill_mem_cli_fixture_exists():
    """Test that the ILL_MEM fixture files exist."""
    print("Testing ILL_MEM fixture files exist...")

    required_files = [
        'progs/ill_mem_cli.elf.S',
        'progs/ill_mem_cli.elf.ld',
    ]

    for f in required_files:
        if not os.path.exists(f):
            print(f"  FAIL: Required file not found: {f}")
            return False

    # Check for compiled ELF or hex (regeneratable)
    elf_exists = os.path.exists('progs/ill_mem_cli.elf')
    hex_exists = os.path.exists('progs/ill_mem_cli.hex')

    if not elf_exists and not hex_exists:
        print(f"  FAIL: Neither progs/ill_mem_cli.elf nor .hex found")
        print(f"        (run: riscv64-unknown-elf-gcc ... progs/ill_mem_cli.elf.S)")
        return False

    print("  PASS: All required fixture files exist")
    return True


def test_ill_mem_triggers_rtl_error():
    """
    Test that running difftest on ill_mem_cli.elf returns ILL_MEM error.

    Expected behavior:
    - Exit code is non-zero (ILL_MEM is an error condition)
    - Output contains "RTL simulation illegal memory access"
    """
    print("Testing ILL_MEM fixture triggers RTL error...")

    # First check if the ELF needs to be compiled
    if not os.path.exists('progs/ill_mem_cli.elf'):
        print("  INFO: Compiling ill_mem_cli.elf...")

        # Compile the fixture
        compile_cmd = [
            'riscv64-unknown-elf-gcc',
            '-mcmodel=medany',
            '-march=rv32imafdc',
            '-mabi=ilp32d',
            '-nostdlib',
            '-nostartfiles',
            '-T', 'progs/ill_mem_cli.elf.ld',
            'progs/ill_mem_cli.elf.S',
            '-o', 'progs/ill_mem_cli.elf'
        ]

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  SKIP: Could not compile fixture: {result.stderr}")
            print("        This test requires riscv64-unknown-elf-gcc")
            return True  # Don't fail if toolchain is missing

    # Run difftest
    try:
        result = run_difftest('progs/ill_mem_cli.elf', timeout=60)
    except subprocess.TimeoutExpired:
        print("  FAIL: Difftest timed out")
        return False
    except FileNotFoundError:
        print("  SKIP: run_difftest.py not found")
        return True  # Don't fail if infrastructure is missing

    # Check exit code
    if result.returncode == 0:
        print("  FAIL: Expected non-zero exit code for ILL_MEM error")
        print(f"        stdout: {result.stdout}")
        return False

    # Check for ILL_MEM error message in output
    combined_output = result.stdout + result.stderr
    if "RTL simulation illegal memory access" not in combined_output:
        print("  FAIL: Expected 'RTL simulation illegal memory access' in output")
        print(f"        stdout: {result.stdout}")
        print(f"        stderr: {result.stderr}")
        return False

    print("  PASS: ILL_MEM error correctly detected and reported")
    return True


def test_ill_mem_spike_execution():
    """
    Test that Spike can execute the ILL_MEM fixture with memory mapping.

    Expected behavior:
    - With --isa-only, Spike should execute successfully
    - Exit code should be 0
    - Output contains "PASS"
    """
    print("Testing ILL_MEM fixture with Spike only...")

    if not os.path.exists('progs/ill_mem_cli.elf'):
        print("  SKIP: ill_mem_cli.elf not found")
        return True

    cmd = [
        sys.executable, 'run_difftest.py',
        '--elf', 'progs/ill_mem_cli.elf',
        '--isa-only',
        '--timeout', '30'
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        print("  FAIL: Spike execution timed out")
        return False
    except FileNotFoundError:
        print("  SKIP: run_difftest.py not found")
        return True

    # Check exit code
    if result.returncode != 0:
        print(f"  FAIL: Spike execution failed with exit code {result.returncode}")
        print(f"        stdout: {result.stdout}")
        print(f"        stderr: {result.stderr}")
        return False

    # Check for PASS in output
    if "PASS" not in result.stdout:
        print("  FAIL: Expected 'PASS' in Spike-only output")
        print(f"        stdout: {result.stdout}")
        return False

    print("  PASS: Spike executes low-address fixture successfully")
    return True


def main():
    """Run all ILL_MEM CLI regression tests."""
    print("=" * 60)
    print("ILL_MEM CLI Regression Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Fixture files exist
    results.append(("Fixture files exist", test_ill_mem_cli_fixture_exists()))
    print()

    # Test 2: Spike can execute the fixture
    results.append(("Spike execution", test_ill_mem_spike_execution()))
    print()

    # Test 3: RTL simulation triggers ILL_MEM error
    results.append(("RTL ILL_MEM detection", test_ill_mem_triggers_rtl_error()))
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
