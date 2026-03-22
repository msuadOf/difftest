"""
ELF utility functions for loading RISC-V ELF files and extracting
information needed for difftest (Spike + RTL simulation comparison).
"""

import os
import subprocess
import struct
import tempfile


DRAM_BASE = 0x80000000


def get_symbols(elf_path):
    """
    Extract symbol table from an ELF file using `nm`.
    Returns a dict mapping symbol names to their addresses.
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    result = subprocess.run(
        ['riscv64-unknown-elf-nm', elf_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        result = subprocess.run(
            ['nm', elf_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to extract symbols from {elf_path}: {result.stderr}")

    symbols = {}
    for line in result.stdout.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 3:
            addr_str = parts[0]
            sym_name = parts[2]
            try:
                symbols[sym_name] = int(addr_str, 16)
            except ValueError:
                continue

    return symbols


def elf_to_flat_hex(elf_path, output_hex_path=None):
    """
    Convert an ELF file to flat hex format (one 64-bit word per line,
    as expected by RTLSim/host.py). Uses objcopy to extract binary,
    then converts to hex.

    Returns the path to the generated hex file.
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    if output_hex_path is None:
        base = os.path.splitext(elf_path)[0]
        output_hex_path = base + '.flat.hex'

    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, 'output.bin')

        # Try riscv64-unknown-elf-objcopy first, then riscv64-linux-gnu-objcopy
        objcopy_cmds = [
            'riscv64-unknown-elf-objcopy',
            'riscv64-linux-gnu-objcopy',
            'objcopy'
        ]

        converted = False
        for objcopy in objcopy_cmds:
            ret = subprocess.run(
                [objcopy, elf_path, '-O', 'binary', bin_path],
                capture_output=True
            )
            if ret.returncode == 0:
                converted = True
                break

        if not converted:
            raise RuntimeError(f"Failed to convert ELF to binary. Tried: {objcopy_cmds}")

        # Read binary and convert to 64-bit hex words
        with open(bin_path, 'rb') as f:
            data = f.read()

    # Pad to 8-byte alignment
    if len(data) % 8 != 0:
        data += b'\x00' * (8 - len(data) % 8)

    lines = []
    for i in range(0, len(data), 8):
        word = struct.unpack_from('<Q', data, i)[0]
        lines.append(f'{word:016x}')

    with open(output_hex_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    return output_hex_path


def elf_to_memory_dict(elf_path):
    """
    Load an ELF file into a memory dictionary {addr: 64-bit value}
    suitable for RTL simulation.
    Uses readelf to find loadable segments and objcopy to extract binary data.
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    # Get program header info to determine load address
    result = subprocess.run(
        ['riscv64-unknown-elf-readelf', '-l', elf_path],
        capture_output=True, text=True
    )

    load_addr = DRAM_BASE  # default
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            stripped = line.strip()
            if stripped.startswith('LOAD'):
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        load_addr = int(parts[2], 16)
                    except ValueError:
                        pass
                    break

    # Convert to binary
    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, 'output.bin')
        objcopy_cmds = [
            'riscv64-unknown-elf-objcopy',
            'riscv64-linux-gnu-objcopy',
        ]
        converted = False
        for objcopy in objcopy_cmds:
            ret = subprocess.run(
                [objcopy, elf_path, '-O', 'binary', bin_path],
                capture_output=True
            )
            if ret.returncode == 0:
                converted = True
                break

        if not converted:
            raise RuntimeError("Failed to convert ELF to binary")

        with open(bin_path, 'rb') as f:
            data = f.read()

    if not data:
        raise ValueError(f"ELF file {elf_path} produced empty binary data")

    # Pad to 8-byte alignment
    if len(data) % 8 != 0:
        data += b'\x00' * (8 - len(data) % 8)

    memory = {}
    for i in range(0, len(data), 8):
        addr = load_addr + i
        word = struct.unpack_from('<Q', data, i)[0]
        memory[addr] = word

    return memory


def has_signature_symbols(symbols):
    """
    Check if the ELF has DifuzzRTL signature infrastructure symbols.
    Returns True if begin_signature, end_signature, tohost, reg_x0_output exist.
    """
    required = ['begin_signature', 'end_signature', 'tohost', 'reg_x0_output']
    return all(sym in symbols for sym in required)


def get_elf_end_addr(symbols, memory):
    """
    Determine the end address of the program code.
    Uses _end_main if available, otherwise computes from memory dict.
    """
    if '_end_main' in symbols:
        return symbols['_end_main']

    if '__bss_start' in symbols:
        return symbols['__bss_start']

    if memory:
        return max(memory.keys()) + 8

    return symbols.get('_start', DRAM_BASE) + 0x1000


def get_elf_isa_width(elf_path):
    """
    Detect the ISA width (32 or 64 bits) from an ELF file.

    Returns:
        'rv32' for 32-bit RISC-V ELF
        'rv64' for 64-bit RISC-V ELF
        None if cannot determine

    Raises:
        ValueError: If the file is not a valid ELF or not RISC-V architecture
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    # Use readelf to get ELF header information
    result = subprocess.run(
        ['riscv64-unknown-elf-readelf', '-h', elf_path],
        capture_output=True, text=True
    )

    # Fallback to system readelf
    if result.returncode != 0:
        result = subprocess.run(
            ['readelf', '-h', elf_path],
            capture_output=True, text=True
        )

    if result.returncode != 0:
        raise ValueError(f"Failed to read ELF header: {elf_path}")

    # Check for RISC-V architecture
    if 'RISC-V' not in result.stdout:
        raise ValueError(f"Not a RISC-V ELF file: {elf_path}")

    # Determine if 32-bit or 64-bit from the ELF class
    for line in result.stdout.split('\n'):
        if 'Class:' in line:
            if 'ELF32' in line:
                return 'rv32'
            elif 'ELF64' in line:
                return 'rv64'

    # Fallback: check machine field
    for line in result.stdout.split('\n'):
        if 'Machine:' in line:
            if 'RISC-V' in line:
                # Default to 32-bit if can't determine
                return 'rv32'

    return None
