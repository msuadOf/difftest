"""
RTL simulation runner for difftest.

This module provides functions to run RTL simulation using cocotb
and the existing DifuzzRTL infrastructure.
"""

import os
import subprocess
import sys
import tempfile
import json


# Result codes matching RTLSim/host.py
SUCCESS = 0
ASSERTION_FAIL = 1
TIME_OUT = 2
ILL_MEM = -1


def run_rtl_simulation(rtl_input, rtl_sig_path, vfile='RocketTile_state',
                       debug=False, timeout=120):
    """
    Run RTL simulation using cocotb and the existing DifuzzRTL infrastructure.

    This function uses the single_program_test.py module under difuzz-rtl/Fuzzer
    to run the simulation, passing parameters through environment variables.

    Args:
        rtl_input: rtlInput object with hexfile, intrfile, data, symbols, max_cycles
        rtl_sig_path: Path where RTL signature file should be written
        vfile: Verilog top-level file name (default: 'E RocketTile_VHarness')
        debug: Enable verbose output (default: False)
        timeout: Simulation timeout in seconds (default: 120)

    Returns:
        Tuple of (result_code, diagnostics) where:
        - result_code: SUCCESS (0), ASSERTION_FAIL (1), TIME_OUT (2), or ILL_MEM (-1)
        - diagnostics: dict with 'make_exit_code', 'stdout_tail', 'stderr_tail' keys
    """
    # Ensure the RTL input hex file exists
    if not os.path.isfile(rtl_input.hexfile):
        raise FileNotFoundError(f"RTL hex file not found: {rtl_input.hexfile}")

    # Get the DifuzzRTL directory
    fuzzer_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'difuzz-rtl', 'Fuzzer'
    )

    makefile_path = os.path.join(fuzzer_dir, 'Makefile')
    if not os.path.isfile(makefile_path):
        raise RuntimeError(f"DifuzzRTL Makefile not found: {makefile_path}")

    # Check if single_program_test.py exists
    test_module_path = os.path.join(fuzzer_dir, 'single_program_test.py')
    if not os.path.isfile(test_module_path):
        raise RuntimeError(f"Single program test module not found: {test_module_path}")

    # Create a temporary config file to pass parameters to the test
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name

    config = {
        'hexfile': os.path.abspath(rtl_input.hexfile),
        'intrfile': os.path.abspath(rtl_input.intrfile) if rtl_input.intrfile else None,
        'data': rtl_input.data,
        'symbols': {k: v for k, v in rtl_input.symbols.items()},
        'max_cycles': rtl_input.max_cycles,
        'debug': debug,
    }

    with open(config_path, 'w') as f:
        json.dump(config, f)

    try:
        # Set up environment variables for cocotb
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{fuzzer_dir}/src:{fuzzer_dir}/RTLSim/src:{env.get('PYTHONPATH', '')}"
        env['RTL_CONFIG_FILE'] = config_path
        env['RTL_SIG_FILE'] = os.path.abspath(rtl_sig_path)
        env['TOPLEVEL_LANG'] = 'verilog'
        # Set TOPLEVEL to match info file (e.g., "RocketTile" for RocketTile_info.txt)
        env['TOPLEVEL'] = vfile.split()[1] if " " in vfile else vfile
        # Strip _state suffix if present to match info file name
        if env['TOPLEVEL'].endswith('_state'):
            env['TOPLEVEL'] = env['TOPLEVEL'][:-6]  # Remove '_state' (6 characters)

        # Build the make command to run the single program test
        make_cmd = [
            'make',
            '-C', fuzzer_dir,
            'SIM=verilator',
            f'VFILE={vfile.split()[1] if " " in vfile else vfile}',
            'MODULE=single_program_test',
        ]

        if debug:
            make_cmd.append('DEBUG=1')

        # Run the simulation
        if debug:
            print(f'[RTL Runner] Running: {" ".join(make_cmd)}')
            print(f'[RTL Runner] Config: {config_path}')

        result = subprocess.run(
            make_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=fuzzer_dir
        )

        if debug:
            if result.stdout:
                print(f'[RTL Runner] STDOUT: {result.stdout[-1000:]}')  # Last 1000 chars
            if result.stderr:
                print(f'[RTL Runner] STDERR: {result.stderr[-1000:]}')

        # Check if the RTL signature file was created
        if not os.path.isfile(rtl_sig_path):
            # Simulation failed to produce signature
            # Make/build failures should be ASSERTION_FAIL, not TIME_OUT
            # Only subprocess.TimeoutExpired should return TIME_OUT
            if result.returncode == 0:
                # Make succeeded but no signature file - this is unexpected
                return (ASSERTION_FAIL, {'make_exit_code': 0, 'stderr_tail': 'No signature file produced'})
            # Make failed with non-zero exit code
            return (ASSERTION_FAIL, {'make_exit_code': result.returncode, 'stderr_tail': result.stderr[-500:] if result.stderr else ''})

        # Return the actual result code from the simulation
        # The test exits with the result code, so returncode is the simulation result
        return (result.returncode, {'make_exit_code': result.returncode})

    except subprocess.TimeoutExpired:
        return (TIME_OUT, {'make_exit_code': None, 'stderr_tail': 'Timeout'})
    except Exception as e:
        if debug:
            print(f'[RTL Runner] Exception: {e}')
        return (ASSERTION_FAIL, {'make_exit_code': None, 'stderr_tail': str(e)})
    finally:
        # Clean up temporary config file
        if os.path.exists(config_path):
            os.unlink(config_path)


def run_rtl_simulation_simple(hex_file, symbols, rtl_sig_path,
                               data=None, max_cycles=10000, debug=False):
    """
    Simplified RTL simulation runner for basic difftest usage.

    Args:
        hex_file: Path to the hex file containing the program
        symbols: Symbol dictionary from the wrapped ELF
        rtl_sig_path: Path where RTL signature file should be written
        data: Optional list of data words (defaults to empty list)
        max_cycles: Maximum simulation cycles (default: 10000)
        debug: Enable verbose output (default: False)

    Returns:
        Result code: SUCCESS (0), ASSERTION_FAIL (1), TIME_OUT (2), or ILL_MEM (-1)
    """
    if data is None:
        data = []

    # Create a simple rtlInput object
    class SimpleRTLInput:
        def __init__(self):
            self.hexfile = hex_file
            self.intrfile = None
            self.data = data
            self.symbols = symbols
            self.max_cycles = max_cycles

    rtl_input = SimpleRTLInput()

    result, _ = run_rtl_simulation(rtl_input, rtl_sig_path, debug=debug)

    return result
