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

    # Check if build directory exists (to determine if we need to compile)
    sim_build_dir = os.path.join(fuzzer_dir, 'sim_build')
    needs_compile = not os.path.exists(os.path.join(sim_build_dir, 'Vtop'))

    # Adjust timeout for clean builds (compilation takes time)
    # Use a minimum of 10 minutes for clean builds, otherwise use specified timeout
    if needs_compile:
        actual_timeout = max(timeout, 600)  # At least 10 minutes for clean builds
    else:
        actual_timeout = timeout

    try:
        # Set up environment variables for cocotb
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{fuzzer_dir}/src:{fuzzer_dir}/RTLSim/src:{env.get('PYTHONPATH', '')}"
        env['RTL_CONFIG_FILE'] = config_path
        env['RTL_SIG_FILE'] = os.path.abspath(rtl_sig_path)
        env['TOPLEVEL_LANG'] = 'verilog'
        # Set TOPLEVEL to match info file (e.g., "RocketTile" for RocketTile_info.txt)
        # For SmallBoomTile_v1.2_state -> BoomTile, RocketTile_state -> RocketTile
        vfile_name = vfile.split()[1] if " " in vfile else vfile
        if 'SmallBoomTile' in vfile_name:
            env['TOPLEVEL'] = 'BoomTile'
        elif vfile_name.endswith('_state'):
            env['TOPLEVEL'] = vfile_name[:-6]  # Remove '_state' (6 characters)
        else:
            env['TOPLEVEL'] = vfile_name
        # Create result file for communicating RTL result back from test
        env['RTL_RESULT_FILE'] = os.path.abspath(os.path.join(
            os.path.dirname(rtl_sig_path), 'rtl_result.txt'))

        # Export RTL_DEBUG for host-level tracing in single_program_test.py
        if debug:
            env['RTL_DEBUG'] = '1'

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
            timeout=actual_timeout,
            env=env,
            cwd=fuzzer_dir
        )

        if debug:
            if result.stdout:
                print(f'[RTL Runner] STDOUT: {result.stdout[-1000:]}')  # Last 1000 chars
            if result.stderr:
                print(f'[RTL Runner] STDERR: {result.stderr[-1000:]}')

        # Prepare diagnostics with stdout/stderr tails
        stdout_tail = result.stdout[-500:] if result.stdout else ''
        stderr_tail = result.stderr[-500:] if result.stderr else ''

        # Read the actual RTL simulation result from RTL_RESULT_FILE
        # The test writes its result code to this file
        rtl_result_path = env.get('RTL_RESULT_FILE')
        actual_result = ASSERTION_FAIL  # Default to assertion fail if we can't determine result

        # IMPORTANT: Only read rtl_result.txt if make succeeded
        # If make failed, any existing rtl_result.txt is stale from a previous run
        if result.returncode != 0:
            # Make failed - don't trust any stale rtl_result.txt
            if debug:
                print(f'[RTL Runner] Make failed with exit code {result.returncode}, ignoring stale result file')
            return (ASSERTION_FAIL, {
                'make_exit_code': result.returncode,
                'stdout_tail': stdout_tail,
                'stderr_tail': stderr_tail or 'Make failed'
            })

        if os.path.isfile(rtl_result_path):
            try:
                with open(rtl_result_path, 'r') as f:
                    result_str = f.read().strip()
                    actual_result = int(result_str)
                if debug:
                    print(f'[RTL Runner] Read result from file: {actual_result}')
            except Exception as e:
                if debug:
                    print(f'[RTL Runner] Error reading result file: {e}')
                actual_result = ASSERTION_FAIL
        else:
            if debug:
                print(f'[RTL Runner] Result file not found: {rtl_result_path}')
            # Result file doesn't exist - check if signature was created
            if not os.path.isfile(rtl_sig_path):
                # No signature file and no result file - simulation failed early
                return (ASSERTION_FAIL, {
                    'make_exit_code': result.returncode,
                    'stdout_tail': stdout_tail,
                    'stderr_tail': stderr_tail or 'No signature or result file'
                })

        # Return the actual simulation result code from the result file
        return (actual_result, {
            'make_exit_code': result.returncode,
            'rtl_result': actual_result,
            'stdout_tail': stdout_tail,
            'stderr_tail': stderr_tail
        })

    except subprocess.TimeoutExpired:
        return (TIME_OUT, {
            'make_exit_code': None,
            'stdout_tail': '',
            'stderr_tail': 'Timeout'
        })
    except Exception as e:
        if debug:
            print(f'[RTL Runner] Exception: {e}')
        return (ASSERTION_FAIL, {
            'make_exit_code': None,
            'stdout_tail': '',
            'stderr_tail': str(e)
        })
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
