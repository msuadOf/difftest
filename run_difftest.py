#!/usr/bin/env python3
"""
run_difftest.py - End-to-end difftest runner for RISC-V ELF files.

Wraps bare ELF binaries with DifuzzRTL signature infrastructure,
runs them through Spike (ISA reference) and optionally RTL simulation,
then compares the execution signatures.

Usage:
    python run_difftest.py --elf progs/xxx.elf
    python run_difftest.py --progs-dir progs/ [--pattern "*.elf"]
"""

import argparse
import glob
import os
import sys
import tempfile

from elf_utils import get_symbols, has_signature_symbols, get_elf_isa_width, bin_to_elf
from elf_wrapper import wrap_elf_for_difftest
from spike_runner import run_spike, find_spike

# Import signature_checker from DifuzzRTL
import sys
fuzzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'difuzz-rtl', 'Fuzzer')
src_path = os.path.join(fuzzer_path, 'src')
sys.path.insert(0, src_path)
sys.path.insert(0, fuzzer_path)
from signature_checker import sigChecker


def run_single_difftest(elf_path, output_dir=None, rtl_sig_file=None, debug=False, timeout=30):
    """
    Run difftest on a single ELF file.

    Args:
        elf_path: Path to the ELF file
        output_dir: Directory for output files
        rtl_sig_file: Optional pre-generated RTL signature for comparison
        debug: Enable verbose output
        timeout: Spike timeout in seconds

    Returns dict with:
        'elf': original ELF path
        'status': 'PASS', 'MISMATCH', 'SPIKE_FAIL', 'WRAP_FAIL', 'ERROR'
        'details': description string
        'isa_sig': path to ISA signature file (if generated)
        'comparison': signature comparison result (if comparison performed)
    """
    result = {
        'elf': elf_path,
        'status': 'ERROR',
        'details': '',
        'isa_sig': None,
        'comparison': None,
    }

    if not os.path.isfile(elf_path):
        result['details'] = f'ELF file not found: {elf_path}'
        return result

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix='difftest_')

    basename = os.path.splitext(os.path.basename(elf_path))[0]

    # Check if input is a .bin file and convert to ELF first
    is_bin_file = elf_path.lower().endswith('.bin')

    if is_bin_file:
        if debug:
            print(f'[Difftest] Converting .bin file to ELF format...')
        try:
            # For .bin files, we need to infer ISA width
            # Default to rv64 for binaries, user can override if needed
            isa_width = 'rv64'  # Default assumption
            # Convert .bin to minimal ELF with basic symbols
            converted_elf = bin_to_elf(elf_path, output_dir=output_dir, isa_width=isa_width)
            if debug:
                print(f'[Difftest] Converted .bin to ELF: {converted_elf}')
            elf_path = converted_elf  # Use the converted ELF for further processing
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'] = f'Failed to convert .bin to ELF: {e}'
            return result

    try:
        # First verify it's a RISC-V ELF
        isa_width = get_elf_isa_width(elf_path)
        symbols = get_symbols(elf_path)
    except ValueError as e:
        result['status'] = 'ERROR'
        result['details'] = f'Not a valid RISC-V ELF file: {e}'
        return result
    except Exception as e:
        result['details'] = f'Failed to read symbols: {e}'
        return result

    if has_signature_symbols(symbols):
        # ELF already has signature infrastructure, use directly
        wrapped_elf = elf_path
        wrapped_symbols = symbols
        if debug:
            print(f'[Difftest] ELF already has signature symbols, using directly')
    else:
        # Wrap bare ELF with signature infrastructure
        if debug:
            print(f'[Difftest] Wrapping bare ELF with signature infrastructure...')
        try:
            wrap_result = wrap_elf_for_difftest(elf_path, output_dir)
            wrapped_elf = wrap_result['elf']
            wrapped_symbols = wrap_result['symbols']
            if debug:
                print(f'[Difftest] Wrapped ELF: {wrapped_elf}')
        except Exception as e:
            result['status'] = 'WRAP_FAIL'
            result['details'] = f'Failed to wrap ELF: {e}'
            return result

    # Map ISA width to Spike ISA string (isa_width was detected earlier)
    if isa_width == 'rv32':
        spike_isa = 'RV32IMAFDC'
    else:
        spike_isa = 'RV64IMAFDC'

    if debug:
        print(f'[Difftest] Detected ISA: {isa_width}, using Spike ISA: {spike_isa}')

    # Run Spike on the wrapped ELF
    isa_sig_path = os.path.join(output_dir, basename + '_isa_sig.txt')
    try:
        spike_rc, isa_sig = run_spike(
            wrapped_elf,
            sig_file=isa_sig_path,
            isa=spike_isa,
            timeout=timeout,
            debug=debug
        )
    except FileNotFoundError as e:
        result['status'] = 'ERROR'
        result['details'] = str(e)
        return result

    result['isa_sig'] = isa_sig

    if spike_rc != 0:
        result['status'] = 'SPIKE_FAIL'
        result['details'] = f'Spike returned non-zero exit code: {spike_rc}'
        return result

    if not os.path.isfile(isa_sig) or os.path.getsize(isa_sig) == 0:
        result['status'] = 'SPIKE_FAIL'
        result['details'] = 'Spike did not produce a signature file'
        return result

    # Perform signature comparison
    # Note: RTL signature file is required for comparison
    if rtl_sig_file is None:
        result['status'] = 'SPIKE_OK'
        result['details'] = (
            f'Spike execution successful. '
            f'Signature: {isa_sig} ({os.path.getsize(isa_sig)} bytes). '
            f'RTL signature file required for comparison (--rtl-sig option).'
        )
        return result

    # Check if RTL signature file exists
    if not os.path.isfile(rtl_sig_file):
        result['status'] = 'ERROR'
        result['details'] = f'RTL signature file not found: {rtl_sig_file}'
        return result

    # Use DifuzzRTL's signature checker
    try:
        checker = sigChecker(isa_sig, rtl_sig_file, debug=debug, minimizing=False)
        match = checker.check(wrapped_symbols)

        if match:
            result['status'] = 'PASS'
            result['details'] = 'All signatures match (ISA and RTL)'
        else:
            result['status'] = 'MISMATCH'
            result['details'] = 'Signature mismatch detected between ISA and RTL'
    except Exception as e:
        result['status'] = 'ERROR'
        result['details'] = f'Signature comparison failed: {e}'

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Run difftest on RISC-V ELF files'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--elf', type=str, help='Path to a single ELF file')
    group.add_argument('--progs-dir', type=str,
                       help='Directory containing ELF files')

    parser.add_argument('--pattern', type=str, default='*.elf',
                        help='Glob pattern for ELF files (default: *.elf)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory for wrapped files and signatures')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Spike timeout in seconds (default: 30)')
    parser.add_argument('--rtl-sig', type=str, default=None,
                        help='Pre-generated RTL signature file for comparison')
    parser.add_argument('--debug', action='store_true',
                        help='Enable verbose debug output')

    args = parser.parse_args()

    # Find spike early to fail fast
    try:
        spike_path = find_spike()
        if args.debug:
            print(f'[Difftest] Using spike: {spike_path}')
    except FileNotFoundError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    # Collect ELF files
    if args.elf:
        elf_files = [args.elf]
    else:
        pattern = os.path.join(args.progs_dir, args.pattern)
        elf_files = sorted(glob.glob(pattern))
        if not elf_files:
            print(f'No ELF files found matching: {pattern}', file=sys.stderr)
            sys.exit(1)

    # Set up output directory
    output_base = args.output_dir
    if output_base is None:
        output_base = tempfile.mkdtemp(prefix='difftest_output_')
    os.makedirs(output_base, exist_ok=True)

    if args.debug:
        print(f'[Difftest] Output directory: {output_base}')
        print(f'[Difftest] Processing {len(elf_files)} ELF file(s)')

    # Run difftest on each file
    results = []
    for elf_path in elf_files:
        basename = os.path.splitext(os.path.basename(elf_path))[0]
        elf_output_dir = os.path.join(output_base, basename)
        os.makedirs(elf_output_dir, exist_ok=True)

        print(f'[{basename}] Running difftest...')
        result = run_single_difftest(
            elf_path,
            output_dir=elf_output_dir,
            rtl_sig_file=args.rtl_sig,
            debug=args.debug,
            timeout=args.timeout
        )
        results.append(result)

        status = result['status']
        if status == 'PASS':
            print(f'[{basename}] PASS')
        elif status == 'MISMATCH':
            print(f'[{basename}] MISMATCH: {result["details"]}')
        elif status == 'SPIKE_OK':
            print(f'[{basename}] SPIKE_OK: {result["details"]}')
        else:
            print(f'[{basename}] {status}: {result["details"]}')

    # Summary
    print('\n' + '=' * 60)
    print('DIFFTEST SUMMARY')
    print('=' * 60)

    counts = {}
    for r in results:
        s = r['status']
        counts[s] = counts.get(s, 0) + 1

    total = len(results)
    for status, count in sorted(counts.items()):
        print(f'  {status}: {count}/{total}')

    print(f'  Total: {total}')
    print(f'  Output: {output_base}')

    # Exit code: 0 if all pass, 1 if any failures
    if all(r['status'] == 'PASS' for r in results):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
