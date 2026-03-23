"""
Single-program RTL test for difftest.

This module provides a dedicated cocotb test that can run a single
program with a given rtlInput and generate an RTL signature file.

This can be invoked through the Makefile with environment variables
to specify the input parameters.
"""

import os
import sys
import json

# Add Fuzzer paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'RTLSim', 'src'))

import cocotb
from cocotb.triggers import Timer, RisingEdge
from RTLSim.host import rvRTLhost, rtlInput, SUCCESS, ASSERTION_FAIL, TIME_OUT, ILL_MEM


def get_rtl_input_from_env():
    """
    Read rtlInput parameters from environment variables.

    Expected environment variables:
    - RTL_CONFIG_FILE: Path to JSON config file with rtlInput parameters
    - RTL_HEX_FILE: Path to hex file (overrides config)
    - RTL_SIG_FILE: Path to output RTL signature file (overrides config)
    - RTL_SYMBOLS: JSON string of symbols dict (overrides config)
    - RTL_MAX_CYCLES: Max cycles (overrides config)
    - RTL_DEBUG: Enable debug output (overrides config)

    Returns:
        rtlInput object or None if not configured
    """
    # Try JSON config file first
    config_path = os.environ.get('RTL_CONFIG_FILE')
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)

            return rtlInput(
                hexfile=config.get('hexfile'),
                intrfile=config.get('intrfile'),
                data=config.get('data', []),
                symbols=config.get('symbols', {}),
                max_cycles=config.get('max_cycles', 10000)
            )
        except Exception as e:
            print(f"Error loading RTL config from {config_path}: {e}")
            return None

    # Fall back to individual environment variables
    hex_file = os.environ.get('RTL_HEX_FILE')
    sig_file = os.environ.get('RTL_SIG_FILE')
    symbols_str = os.environ.get('RTL_SYMBOLS')
    max_cycles = os.environ.get('RTL_MAX_CYCLES', '10000')

    if hex_file and sig_file and symbols_str:
        try:
            symbols = json.loads(symbols_str)
            return rtlInput(
                hexfile=hex_file,
                intrfile=None,
                data=[],
                symbols=symbols,
                max_cycles=int(max_cycles)
            )
        except Exception as e:
            print(f"Error parsing RTL environment: {e}")
            return None

    return None


@cocotb.test()
async def test(dut):
    """
    Run a single program RTL test.

    This test reads rtlInput parameters from environment variables,
    runs the RTL simulation, and writes the RTL signature file.

    The test exits with the result code:
    - SUCCESS (0): Simulation completed successfully
    - ASSERTION_FAIL (1): Assertion failure occurred
    - TIME_OUT (2): Simulation timed out
    - ILL_MEM (-1): Illegal memory access detected
    """
    # Get rtlInput from environment
    rtl_input = get_rtl_input_from_env()

    # Get result file path early - we need it for error reporting
    rtl_result_file = os.environ.get('RTL_RESULT_FILE')

    def write_error_result(result_code):
        """Helper function to write error result to file."""
        if rtl_result_file:
            try:
                with open(rtl_result_file, 'w') as f:
                    f.write(str(result_code))
            except:
                pass

    if rtl_input is None:
        print("ERROR: No RTL input configuration found")
        print("Set RTL_CONFIG_FILE environment variable with JSON config")
        print("Or set RTL_HEX_FILE, RTL_SIG_FILE, and RTL_SYMBOLS environment variables")
        write_error_result(ASSERTION_FAIL)
        return  # Exit the test gracefully

    # Get output path
    rtl_sig_path = os.environ.get('RTL_SIG_FILE')
    if not rtl_sig_path:
        print("ERROR: RTL_SIG_FILE environment variable not set")
        write_error_result(ASSERTION_FAIL)
        return  # Exit the test gracefully

    if not rtl_result_file:
        print("ERROR: RTL_RESULT_FILE environment variable not set")
        # Can't write result file if path not set
        return  # Exit the test gracefully

    # Get debug flag
    debug = os.environ.get('RTL_DEBUG', '0') == '1'

    # Get toplevel name - must match info file name (e.g., "RocketTile" for RocketTile_info.txt)
    toplevel = os.environ.get('TOPLEVEL', 'RocketTile')

    try:
        # Create RTL host
        host = rvRTLhost(
            dut=dut,
            toplevel=toplevel,
            rtl_sig_file=rtl_sig_path,
            debug=debug
        )

        # Run the simulation
        result, _ = await host.run_test(rtl_input, assert_intr=False)

        # Write result to status file for rtl_runner.py to read
        try:
            with open(rtl_result_file, 'w') as f:
                f.write(str(result))
            if debug:
                print(f"RTL simulation completed with result: {result}")
                print(f"Result written to: {rtl_result_file}")
        except Exception as e:
            if debug:
                print(f"ERROR writing result file: {e}")

        # Exit successfully (cocotb 2.0 treats SystemExit as failure)
        # The result is now communicated via the status file

    except Exception as e:
        print(f"ERROR during RTL simulation: {e}")
        import traceback
        traceback.print_exc()
        # Write error status to file
        write_error_result(ASSERTION_FAIL)
        # Let cocotb handle the exception naturally
        raise
