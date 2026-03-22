"""
RTL input bundle builder for difftest.

This module provides functions to build the rtlInput object needed
for cocotb RTL simulation using the wrapped ELF.
"""

import os
import struct


def build_rtl_input_bundle(wrapped_elf_path, wrapped_hex_path, symbols,
                           intrfile=None, max_cycles=10000):
    """
    Build an rtlInput object for cocotb RTL simulation.

    Args:
        wrapped_elf_path: Path to the wrapped ELF file
        wrapped_hex_path: Path to the wrapped hex file
        symbols: Symbol dictionary from the wrapped ELF
        intrfile: Path to interrupt file (optional, defaults to None)
        max_cycles: Maximum simulation cycles (default: 10000)

    Returns:
        rtlInput object with fields: hexfile, intrfile, data, symbols, max_cycles
    """
    if not os.path.isfile(wrapped_hex_path):
        raise FileNotFoundError(f"Hex file not found: {wrapped_hex_path}")

    # Extract data words from the _random_data sections
    # The data sections are populated from the original ELF's data sections
    data = _extract_data_words_from_symbols(symbols, hex_file=wrapped_hex_path)

    # Create rtlInput object (simple class for compatibility)
    class rtlInput:
        def __init__(self, hexfile, intrfile, data, symbols, max_cycles):
            self.hexfile = hexfile
            self.intrfile = intrfile
            self.data = data
            self.symbols = symbols
            self.max_cycles = max_cycles

    return rtlInput(
        hexfile=wrapped_hex_path,
        intrfile=intrfile,
        data=data,
        symbols=symbols,
        max_cycles=max_cycles
    )


def _extract_data_words_from_symbols(symbols, hex_file=None):
    """
    Extract data words from the _random_data symbols in the wrapped ELF.

    The wrapper populates _random_data0..5 sections with data from the
    original ELF's .data/.rodata sections. This function extracts those
    data words as a flat list of 64-bit integers.

    Args:
        symbols: Symbol dictionary from the wrapped ELF
        hex_file: Optional path to the wrapped hex file for reading actual data

    Returns:
        List of 64-bit integers representing the data words
    """
    from elf_utils import elf_to_memory_dict

    data_words = []

    # If we have the hex file, we can extract the actual data values
    if hex_file and os.path.isfile(hex_file):
        try:
            # Load the wrapped ELF to get the actual memory contents
            # We need to find the wrapped ELF path (same stem as hex file)
            elf_path = os.path.splitext(hex_file)[0] + '.elf'
            if os.path.isfile(elf_path):
                memory = elf_to_memory_dict(elf_path)

                for i in range(6):
                    data_start_sym = f'_random_data{i}'
                    data_end_sym = f'_end_data{i}'

                    if data_start_sym in symbols and data_end_sym in symbols:
                        data_start = symbols[data_start_sym]
                        data_end = symbols[data_end_sym]

                        # Extract data words from memory, 8-byte aligned
                        addr = data_start & ~0x7  # Align down to 8 bytes
                        end_addr = data_end

                        while addr < end_addr:
                            if addr in memory:
                                data_words.append(memory[addr])
                            addr += 8
        except Exception as e:
            # If extraction fails, fall back to placeholder
            pass

    # Fallback: if we couldn't extract actual data, use section sizes for placeholders
    if not data_words:
        for i in range(6):
            data_start_sym = f'_random_data{i}'
            data_end_sym = f'_end_data{i}'

            if data_start_sym in symbols and data_end_sym in symbols:
                data_start = symbols[data_start_sym]
                data_end = symbols[data_end_sym]

                # Calculate size in 64-bit words
                size_bytes = data_end - data_start
                size_words = size_bytes // 8

                # Add placeholders for this data section
                for _ in range(size_words):
                    data_words.append(0)

    return data_words


def get_data_section_sizes(symbols):
    """
    Get the sizes of the _random_data sections for RTL simulation setup.

    Args:
        symbols: Symbol dictionary from the wrapped ELF

    Returns:
        List of tuples (start_addr, end_addr) for each _random_data section
    """
    data_sections = []

    for i in range(6):
        data_start_sym = f'_random_data{i}'
        data_end_sym = f'_end_data{i}'

        if data_start_sym in symbols and data_end_sym in symbols:
            data_start = symbols[data_start_sym]
            data_end = symbols[data_end_sym]
            data_sections.append((data_start, data_end))

    return data_sections
