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
    # Returns (data_words, data_addrs) where data_addrs is a list of (addr, value) tuples
    data_words, data_addrs = _extract_data_words_from_symbols(symbols, elf_path=wrapped_elf_path,
                                                              is_preinstrumented=is_preinstrumented)

    # Create rtlInput object (simple class for compatibility)
    class rtlInput:
        def __init__(self, hexfile, intrfile, data, symbols, max_cycles, data_addrs=None):
            self.hexfile = hexfile
            self.intrfile = intrfile
            self.data = data
            self.symbols = symbols
            self.max_cycles = max_cycles
            self.data_addrs = data_addrs if data_addrs is not None else []

    return rtlInput(
        hexfile=wrapped_hex_path,
        intrfile=intrfile,
        data=data_words,
        symbols=symbols,
        max_cycles=max_cycles,
        data_addrs=data_addrs
    )


def _get_section_headers(elf_path):
    """
    Get section headers from an ELF file.

    Returns a dict mapping section names to (address, size) tuples.
    Only returns allocated sections (SHF_ALLOC) that have non-zero size.
    """
    import subprocess

    if not os.path.isfile(elf_path):
        return {}

    # Use readelf to get section headers
    result = subprocess.run(
        ['riscv64-unknown-elf-readelf', '-S', elf_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        result = subprocess.run(
            ['readelf', '-S', elf_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return {}

    sections = {}
    lines = result.stdout.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith('There are') or line.startswith('Section Headers:') or line.startswith('Key to Flags:'):
            i += 1
            continue

        # Parse readelf output format:
        # Single line format:
        # [ 1] .text             PROGBITS        80000000 001000 000142 00  AX  0   0 64
        # Two line format:
        # [ 1] .text             PROGBITS        80000000 001000
        #      000142 00000000  AX  0   0 64

        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith('['):
            # Check if this is a two-line format
            # Two-line format has exactly 5 columns in the first line
            if len(parts) == 5:
                # First line: [Nr] Name Type Addr Off
                section_name = parts[1]
                addr_str = parts[3]
                # Second line has Size, ES, Flg, Lk, Inf, Al
                if i + 1 < len(lines):
                    next_parts = lines[i + 1].split()
                    if len(next_parts) >= 3:
                        size_str = next_parts[0]
                        flags = next_parts[2] if len(next_parts) > 2 else ''
                        try:
                            addr = int(addr_str, 16)
                            size = int(size_str, 16)
                            if 'A' in flags and size > 0:
                                sections[section_name] = (addr, size)
                        except (ValueError, IndexError):
                            pass
                i += 2
                continue
            else:
                # Single line format: all columns in one line
                # [Nr] Name Type Addr Off Size ES Flg Lk Inf Al
                section_name = parts[1]
                addr_str = parts[3]
                size_str = parts[5]
                flags = parts[7] if len(parts) > 7 else ''
                try:
                    addr = int(addr_str, 16)
                    size = int(size_str, 16)
                    if 'A' in flags and size > 0:
                        sections[section_name] = (addr, size)
                except (ValueError, IndexError):
                    pass
        i += 1

    return sections


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
        Tuple of (data_words, data_addrs) where:
        - data_words: List of 64-bit integers (for compatibility)
        - data_addrs: List of (addr, value) tuples for pre-instrumented ELFs
    """
    from elf_utils import elf_to_memory_dict

    data_words = []
    data_addrs = []  # List of (addr, value) tuples for pre-instrumented ELFs

    # If we have the ELF path, we can extract the actual data values
    if elf_path and os.path.isfile(elf_path):
        try:
            # Load the ELF to get the actual memory contents
            memory = elf_to_memory_dict(elf_path)

            if is_preinstrumented:
                # For pre-instrumented ELFs, extract from ordinary data sections
                # Get section headers from ELF (not from nm symbols)
                section_headers = _get_section_headers(elf_path)

                # Look for .data, .rodata, .sdata, .srodata sections
                data_section_names = ['.data', '.rodata', '.sdata', '.srodata']
                for section_name in data_section_names:
                    if section_name in section_headers:
                        section_start, section_size = section_headers[section_name]
                        section_end = section_start + section_size

                        # Extract data words from memory, 8-byte aligned
                        addr = section_start & ~0x7  # Align down to 8 bytes
                        end_addr = (section_end + 7) & ~0x7  # Round up to 8 bytes

                        while addr < end_addr:
                            if addr in memory:
                                value = memory[addr]
                                data_words.append(value)
                                data_addrs.append((addr, value))
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
                            value = memory[addr]
                            data_words.append(value)
                            # Only add to data_addrs for pre-instrumented ELFs
                            # (wrapped ELFs use the existing _random_data mechanism)
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

    return data_words, data_addrs


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
