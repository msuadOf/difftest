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

    # Check if this is a pre-instrumented ELF (has begin_signature symbol)
    is_preinstrumented = 'begin_signature' in symbols

    # Extract data words from the _random_data sections (for wrapped ELFs)
    # and from ordinary .data/.rodata sections (for pre-instrumented ELFs)
    data = _extract_data_words_from_symbols(symbols, elf_path=wrapped_elf_path,
                                            is_preinstrumented=is_preinstrumented)

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


def _extract_data_words_from_symbols(symbols, elf_path=None, is_preinstrumented=False):
    """
    Extract data words from the ELF for RTL simulation.

    For wrapped ELFs: extracts from _random_data0..5 sections.
    For pre-instrumented ELFs: also extracts from ordinary .data/.rodata sections.

    Args:
        symbols: Symbol dictionary from the ELF
        elf_path: Path to the ELF file for reading actual data
        is_preinstrumented: True if this is a pre-instrumented ELF (has begin_signature)

    Returns:
        List of 64-bit integers representing the data words
    """
    from elf_utils import elf_to_memory_dict

    data_words = []

    # If we have the ELF path, we can extract the actual data values
    if elf_path and os.path.isfile(elf_path):
        try:
            # Load the ELF to get the actual memory contents
            memory = elf_to_memory_dict(elf_path)

            if is_preinstrumented:
                # For pre-instrumented ELFs, extract from ordinary data sections
                # Look for .data, .rodata, .sdata, .srodata sections
                data_section_names = ['.data', '.rodata', '.sdata', '.srodata']
                for section_name in data_section_names:
                    if section_name in symbols:
                        # Find the end of this section
                        # Try common end symbols first
                        end_sym = section_name.replace('.data', '_edata')
                        end_sym_alt = section_name.replace('.data', '_end')
                        if end_sym in symbols:
                            section_end = symbols[end_sym]
                        elif end_sym_alt in symbols:
                            section_end = symbols[end_sym_alt]
                        else:
                            # No explicit end symbol, estimate from next symbol
                            # or use a reasonable maximum size
                            section_start = symbols[section_name]
                            section_end = section_start + 0x1000  # Conservative estimate

                        section_start = symbols[section_name]

                        # Extract data words from memory, 8-byte aligned
                        addr = section_start & ~0x7  # Align down to 8 bytes
                        end_addr = (section_end + 7) & ~0x7  # Round up to 8 bytes

                        while addr < end_addr:
                            if addr in memory:
                                data_words.append(memory[addr])
                            addr += 8

            # Always extract from _random_data sections (for wrapped ELFs)
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
