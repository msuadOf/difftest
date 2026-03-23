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

from elf_utils import get_symbols, has_signature_symbols, get_elf_isa_width, resolve_bin_to_elf, get_spike_memory_map
from elf_wrapper import wrap_elf_for_difftest
from spike_runner import run_spike, find_spike

# Import signature_checker from DifuzzRTL
import sys
fuzzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'difuzz-rtl', 'Fuzzer')
src_path = os.path.join(fuzzer_path, 'src')
sys.path.insert(0, src_path)
sys.path.insert(0, fuzzer_path)
from signature_checker import sigChecker

# Import RTL runner and utilities
try:
    from rtl_runner import run_rtl_simulation, SUCCESS, ASSERTION_FAIL, TIME_OUT, ILL_MEM
    from rtl_input import build_rtl_input_bundle
    RTL_AVAILABLE = True
except ImportError as e:
    RTL_AVAILABLE = False


def run_single_difftest(elf_path, output_dir=None, rtl_sig_file=None, debug=False, timeout=30, isa_only=False, isa_width=None):
    """
    Run difftest on a single ELF file.

    Args:
        elf_path: Path to the ELF file
        output_dir: Directory for output files
        rtl_sig_file: Optional pre-generated RTL signature for comparison
        debug: Enable verbose output
        timeout: Spike timeout in seconds
        isa_only: Run Spike only, skip RTL comparison
        isa_width: Explicit ISA width for .bin files (rv32 or rv64)

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

    # Check if input is a .bin file and resolve to ELF
    is_bin_file = elf_path.lower().endswith('.bin')

    if is_bin_file:
        if debug:
            print(f'[Difftest] Resolving .bin file to ELF...')

        try:
            # Resolve .bin to ELF (uses sibling .elf if available, otherwise generates minimal ELF)
            resolved_elf, isa_width, resolved_symbols = resolve_bin_to_elf(elf_path, isa_width_hint=isa_width)

            if debug:
                print(f'[Difftest] Resolved .bin to ELF: {resolved_elf}')
                print(f'[Difftest] Detected ISA: {isa_width}')

            elf_path = resolved_elf  # Use the resolved ELF for further processing
            # Use the resolved symbols and ISA width directly
            symbols = resolved_symbols

        except Exception as e:
            result['status'] = 'ERROR'
            result['details'] = f'Failed to resolve .bin file: {e}'
            return result

    try:
        # First verify it's a RISC-V ELF
        if not is_bin_file:  # Only detect if we didn't already resolve from .bin
            isa_width = get_elf_isa_width(elf_path)
            symbols = get_symbols(elf_path)
    except ValueError as e:
        result['status'] = 'ERROR'
        result['details'] = f'Not a valid RISC-V ELF file: {e}'
        return result
    except Exception as e:
        result['details'] = f'Failed to read symbols: {e}'
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
        wrapped_hex = elf_path.replace('.elf', '.hex')  # Assume hex exists
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
            wrapped_hex = wrap_result['hex']
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
        # Build Spike extra args for memory map
        spike_extra_args = []
        mem_regions = get_spike_memory_map(wrapped_elf, wrapped_symbols)
        if mem_regions and debug:
            print(f'[Difftest] Memory map regions: {[f"0x{base:x}:0x{size:x}" for base, size in mem_regions]}')

        if mem_regions:
            # Format as -m0x<a>:0x<m>,... (Spike requires 0x prefix)
            mem_map_str = ','.join([f'0x{base:x}:0x{size:x}' for base, size in mem_regions])
            spike_extra_args = [f'-m{mem_map_str}']
            if debug:
                print(f'[Difftest] Spike memory map: -m{mem_map_str}')

        spike_rc, isa_sig = run_spike(
            wrapped_elf,
            sig_file=isa_sig_path,
            isa=spike_isa,
            extra_args=spike_extra_args if spike_extra_args else None,
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
    if isa_only:
        # ISA-only mode: Spike execution succeeded, no RTL comparison
        result['status'] = 'PASS'
        result['details'] = (
            f'ISA-only mode: Spike execution successful. '
            f'Signature: {isa_sig} ({os.path.getsize(isa_sig)} bytes). '
            f'No RTL comparison performed (omit --isa-only for end-to-end difftest).'
        )
        return result

    # End-to-end mode: Check for pre-generated RTL signature or run RTL simulation
    if rtl_sig_file:
        # Use pre-generated RTL signature
        if not os.path.isfile(rtl_sig_file):
            result['status'] = 'ERROR'
            result['details'] = f'Pre-generated RTL signature not found: {rtl_sig_file}'
            return result
        rtl_sig_path = rtl_sig_file
        if debug:
            print(f'[Difftest] Using pre-generated RTL signature: {rtl_sig_path}')
    else:
        # Run RTL simulation
        rtl_sig_path = os.path.join(output_dir, basename + '_rtl_sig.txt')

    # Check if we need to run RTL simulation or use pre-generated signature
    if not rtl_sig_file:
        # Check if RTL runner is available
        if not RTL_AVAILABLE:
            result['status'] = 'ERROR'
            result['details'] = (
                f'RTL runner not available. '
                f'This may be due to missing dependencies (cocotb/verilator). '
                f'Use --isa-only for Spike-only testing, or --rtl-sig for pre-generated RTL signature.'
            )
            return result

        # Build RTL input bundle
        try:
            rtl_input_bundle = build_rtl_input_bundle(
                wrapped_elf_path=wrapped_elf,
                wrapped_hex_path=wrapped_hex,
                symbols=wrapped_symbols,
                max_cycles=timeout * 1000  # Convert seconds to cycles (allow more cycles)
            )
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'] = f'Failed to build RTL input bundle: {e}'
            return result

        # Run RTL simulation
        try:
            if debug:
                print(f'[Difftest] Running RTL simulation...')

            rtl_result_code, diagnostics = run_rtl_simulation(
                rtl_input_bundle,
                rtl_sig_path=rtl_sig_path,
                debug=debug,
                timeout=timeout * 2  # Give RTL more time
            )

            if debug:
                print(f'[Difftest] RTL simulation result: {rtl_result_code}')
                if diagnostics.get('stdout_tail'):
                    print(f'[Difftest] RTL stdout: {diagnostics["stdout_tail"][-200:]}')
                if diagnostics.get('stderr_tail'):
                    print(f'[Difftest] RTL stderr: {diagnostics["stderr_tail"][-200:]}')

            # Check RTL result
            if rtl_result_code == SUCCESS:
                if debug:
                    print(f'[Difftest] RTL simulation successful')
            elif rtl_result_code == TIME_OUT:
                result['status'] = 'ERROR'
                result['details'] = f'RTL simulation timed out. {diagnostics.get("stderr_tail", "")}'
                return result
            elif rtl_result_code == ASSERTION_FAIL:
                result['status'] = 'ERROR'
                make_exit = diagnostics.get('make_exit_code', 'unknown')
                stderr = diagnostics.get('stderr_tail', '')
                stdout = diagnostics.get('stdout_tail', '')
                if make_exit and make_exit != 1:
                    details = f'RTL make/configuration failed (exit code {make_exit})'
                    if stdout:
                        details += f' | stdout: {stdout[-200:]}'
                    if stderr:
                        details += f' | stderr: {stderr[-200:]}'
                    result['details'] = details
                else:
                    result['details'] = f'RTL simulation assertion failure. {stderr[-200:]}'
                return result
            elif rtl_result_code == ILL_MEM:
                result['status'] = 'ERROR'
                result['details'] = 'RTL simulation illegal memory access'
                return result
            else:
                result['status'] = 'ERROR'
                result['details'] = f'RTL simulation failed with code: {rtl_result_code}'
                return result

        except FileNotFoundError as e:
            # RTL simulation not available (cocotb/verilator not set up)
            result['status'] = 'ERROR'
            result['details'] = (
                f'RTL simulation not available: {e}. '
                f'This may be due to missing cocotb/verilator environment. '
                f'Use --isa-only for Spike-only testing, or set up RTL environment.'
            )
            return result
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'] = f'RTL simulation failed: {e}'
            return result

    # Check if RTL signature file was created (only if we ran RTL simulation)
    if not rtl_sig_file and not os.path.isfile(rtl_sig_path):
        result['status'] = 'ERROR'
        result['details'] = 'RTL simulation did not produce signature file'
        return result

    # Use DifuzzRTL's signature checker
    try:
        checker = sigChecker(isa_sig, rtl_sig_path, debug=debug, minimizing=False, isa_width=isa_width)
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

    parser.add_argument('--pattern', type=str, default=None,
                        help='Glob pattern for program files (default: *.elf and *.bin). Can be *.elf, *.bin, or other pattern.')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory for wrapped files and signatures')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Spike timeout in seconds (default: 30)')
    parser.add_argument('--isa-width', type=str, choices=['rv32', 'rv64'], default=None,
                        help='Explicit ISA width for .bin files (rv32 or rv64). Required for standalone .bin files without sibling .elf.')
    parser.add_argument('--rtl-sig', type=str, default=None,
                        help='Pre-generated RTL signature file for comparison (required for end-to-end difftest)')
    parser.add_argument('--isa-only', action='store_true',
                        help='Run Spike only, skip RTL comparison (for testing/debug, not end-to-end difftest)')
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
        # Default to both .elf and .bin files if no pattern specified
        if args.pattern is None:
            patterns = [
                os.path.join(args.progs_dir, '*.elf'),
                os.path.join(args.progs_dir, '*.bin')
            ]
            # Use set to deduplicate in case a file matches both patterns
            elf_files = sorted(set(f for p in patterns for f in glob.glob(p)))
        else:
            pattern = os.path.join(args.progs_dir, args.pattern)
            elf_files = sorted(glob.glob(pattern))

        if not elf_files:
            if args.pattern is None:
                print(f'No ELF or BIN files found in: {args.progs_dir}', file=sys.stderr)
            else:
                print(f'No files found matching: {os.path.join(args.progs_dir, args.pattern)}', file=sys.stderr)
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
            timeout=args.timeout,
            isa_only=args.isa_only,
            isa_width=args.isa_width
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
