"""
Spike ISA simulator runner for difftest.
Wraps ISASim/host.py to run Spike directly with an ELF file.
"""

import os
import subprocess
import tempfile


DEFAULT_SPIKE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'difuzz-rtl', 'Fuzzer', 'ISASim', 'riscv-isa-sim', 'build', 'spike'
)


def find_spike():
    """Find the spike binary. Check SPIKE env var, then built copy, then PATH."""
    if os.environ.get('SPIKE'):
        return os.environ['SPIKE']
    if os.path.isfile(DEFAULT_SPIKE_PATH):
        return DEFAULT_SPIKE_PATH
    # Try PATH
    result = subprocess.run(['which', 'spike'], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    raise FileNotFoundError(
        "Spike not found. Set SPIKE env var or build it from "
        "difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/"
    )


def run_spike(elf_path, sig_file=None, isa='RV64IMAFDC', spike_path=None,
              extra_args=None, timeout=30, debug=False):
    """
    Run Spike ISA simulator on the given ELF file.

    Args:
        elf_path: Path to the RISC-V ELF binary
        sig_file: Path to write signature output (if None, uses temp file)
        isa: ISA string for spike (default: rv32gfd)
        spike_path: Path to spike binary (auto-detected if None)
        extra_args: Additional spike arguments
        timeout: Timeout in seconds
        debug: Enable verbose output

    Returns:
        (return_code, sig_file_path) tuple
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    if spike_path is None:
        spike_path = find_spike()

    if sig_file is None:
        sig_file = tempfile.mktemp(suffix='_isa_sig.txt')

    args = [spike_path]

    if isa:
        args.append(f'--isa={isa}')

    if extra_args:
        args.extend(extra_args)

    args.append(f'+signature={sig_file}')
    args.append(elf_path)

    if debug:
        print(f'[SpikeRunner] Command: {" ".join(args)}')

    try:
        ret = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        rc = ret.returncode
        if debug:
            if ret.stdout:
                print(f'[SpikeRunner] stdout: {ret.stdout[:500]}')
            if ret.stderr:
                print(f'[SpikeRunner] stderr: {ret.stderr[:500]}')
    except subprocess.TimeoutExpired:
        if debug:
            print(f'[SpikeRunner] Timeout after {timeout}s')
        rc = -1

    if debug:
        print(f'[SpikeRunner] Return code: {rc}')
        if os.path.isfile(sig_file):
            size = os.path.getsize(sig_file)
            print(f'[SpikeRunner] Signature file size: {size} bytes')

    return (rc, sig_file)
