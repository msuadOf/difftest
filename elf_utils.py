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

    Uses segment-accurate PT_LOAD-based loading that preserves each
    segment's real virtual address and properly handles BSS regions.
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    # Read the ELF file directly to extract segment data
    with open(elf_path, 'rb') as f:
        elf_data = f.read()

    # Parse ELF header
    if len(elf_data) < 64 or elf_data[:4] != b'\x7fELF':
        raise ValueError(f"Not a valid ELF file: {elf_path}")

    elf_class = elf_data[4]  # 1 = 32-bit, 2 = 64-bit
    elf_endian = '<' if elf_data[5] == 1 else '>'  # 1 = little, 2 = big

    if elf_class == 1:
        # ELF32
        e_phoff_fmt = 'I'
        e_phentsize_fmt = 'H'
        e_phnum_fmt = 'H'
        p_type_fmt = 'I'
        p_offset_fmt = 'I'
        p_vaddr_fmt = 'I'
        p_filesz_fmt = 'I'
        p_memsz_fmt = 'I'
        header_size = 52
    else:
        # ELF64
        e_phoff_fmt = 'Q'
        e_phentsize_fmt = 'H'
        e_phnum_fmt = 'H'
        p_type_fmt = 'I'
        p_offset_fmt = 'Q'
        p_vaddr_fmt = 'Q'
        p_filesz_fmt = 'Q'
        p_memsz_fmt = 'Q'
        header_size = 64

    # Extract program header info from ELF header
    endian_fmt = elf_endian

    # ELF32 and ELF64 have different offsets for these fields
    if elf_class == 1:
        # ELF32 offsets
        e_phoff_offset = 28
        e_phentsize_offset = 42
        e_phnum_offset = 44
    else:
        # ELF64 offsets
        e_phoff_offset = 32
        e_phentsize_offset = 54
        e_phnum_offset = 56

    # Parse program header table location
    fmt_str = endian_fmt + e_phoff_fmt
    e_phoff = struct.unpack_from(fmt_str, elf_data, e_phoff_offset)[0]

    fmt_str = endian_fmt + e_phentsize_fmt
    e_phentsize = struct.unpack_from(fmt_str, elf_data, e_phentsize_offset)[0]

    fmt_str = endian_fmt + e_phnum_fmt
    e_phnum = struct.unpack_from(fmt_str, elf_data, e_phnum_offset)[0]

    # Parse each program header
    load_segments = []
    ph_offset = e_phoff

    if elf_class == 1:
        ph_size = 32
        p_type_offset = 0
        p_offset_offset = 4
        p_vaddr_offset = 8
        p_filesz_offset = 16
        p_memsz_offset = 20
    else:
        ph_size = 56
        p_type_offset = 0
        p_offset_offset = 8
        p_vaddr_offset = 16
        p_filesz_offset = 32
        p_memsz_offset = 40

    for i in range(e_phnum):
        if ph_offset + ph_size > len(elf_data):
            break

        fmt_str = endian_fmt + p_type_fmt
        p_type = struct.unpack_from(fmt_str, elf_data, ph_offset + p_type_offset)[0]

        if p_type == 1:  # PT_LOAD
            fmt_str = endian_fmt + p_offset_fmt
            p_offset = struct.unpack_from(fmt_str, elf_data, ph_offset + p_offset_offset)[0]

            fmt_str = endian_fmt + p_vaddr_fmt
            p_vaddr = struct.unpack_from(fmt_str, elf_data, ph_offset + p_vaddr_offset)[0]

            fmt_str = endian_fmt + p_filesz_fmt
            p_filesz = struct.unpack_from(fmt_str, elf_data, ph_offset + p_filesz_offset)[0]

            fmt_str = endian_fmt + p_memsz_fmt
            p_memsz = struct.unpack_from(fmt_str, elf_data, ph_offset + p_memsz_offset)[0]

            load_segments.append({
                'offset': p_offset,
                'vaddr': p_vaddr,
                'filesz': p_filesz,
                'memsz': p_memsz,
            })

        ph_offset += e_phentsize

    # Load each segment into memory dictionary
    memory = {}

    for seg in load_segments:
        vaddr = seg['vaddr']
        offset = seg['offset']
        filesz = seg['filesz']
        memsz = seg['memsz']

        # Extract file data for this segment
        if offset + filesz <= len(elf_data):
            seg_data = elf_data[offset:offset + filesz]
        else:
            seg_data = b''
            # Read what we can
            if offset < len(elf_data):
                seg_data = elf_data[offset:]

        # Place data at virtual addresses (8-byte aligned)
        aligned_addr = vaddr & ~0x7  # Align down to 8 bytes

        # Handle alignment offset
        addr_offset = vaddr - aligned_addr

        # Create a buffer with alignment padding
        if addr_offset > 0:
            padded_data = b'\x00' * addr_offset + seg_data
        else:
            padded_data = seg_data

        # Pad to 8-byte alignment
        if len(padded_data) % 8 != 0:
            padded_data += b'\x00' * (8 - len(padded_data) % 8)

        # Store file data, preserving existing bytes for partially-overwritten words
        for i in range(0, len(padded_data), 8):
            addr = aligned_addr + i
            if i + 8 <= len(padded_data):
                new_word = struct.unpack_from('<Q', padded_data, i)[0]

                # If this address already has data, merge the new data with existing
                if addr in memory:
                    existing_word = memory[addr]
                    # Calculate which bytes to update
                    for byte_idx in range(8):
                        # Check if this byte position is within the actual segment data
                        seg_byte_pos = i + byte_idx - addr_offset
                        if 0 <= seg_byte_pos < len(seg_data):
                            # Extract byte from new_word
                            new_byte = (new_word >> (byte_idx * 8)) & 0xFF
                            # Clear and set the byte in existing_word
                            byte_mask = 0xFF << (byte_idx * 8)
                            existing_word = (existing_word & ~byte_mask) | (new_byte << (byte_idx * 8))
                    memory[addr] = existing_word
                else:
                    memory[addr] = new_word

        # Zero-fill BSS region (memsz > filesz)
        if memsz > filesz:
            bss_start = vaddr + filesz
            bss_end = vaddr + memsz
            bss_start_aligned = bss_start & ~0x7

            for addr in range(bss_start_aligned, bss_end, 8):
                if addr not in memory:
                    memory[addr] = 0

    if not memory:
        raise ValueError(f"ELF file {elf_path} produced no loadable segments")

    return memory


def memory_dict_to_rtl_hex(memory, symbols, output_hex_path):
    """
    Serialize a memory dictionary to RTL hex format.

    This is the segment-accurate alternative to objcopy-based flattening.
    It preserves each segment's actual virtual address layout while
    emitting the contiguous hex format expected by RTLSim/host.py.

    Args:
        memory: Dictionary {addr: 64-bit value} from elf_to_memory_dict()
        symbols: Symbol dictionary containing _start and _end_main
        output_hex_path: Path where hex file will be written

    Returns:
        output_hex_path (for chaining)

    The emitted format is one 64-bit hex value per line, covering the range
    from _start to _end_main + 36 (the +36 buffer is for post-code data
    like the signature writeout routine).
    """
    _start = symbols.get('_start', 0x80000000)
    _end_main = symbols.get('_end_main', _start + 0x1000)

    # RTL host loads from _start to _end_main + 36 in 8-byte increments
    # Range is [start, stop) so we use _end_main + 36 as stop (excluded)
    lines = []
    for addr in range(_start, _end_main + 36, 8):
        # Get value from memory dict, default to 0 for gaps/unmapped regions
        value = memory.get(addr, 0)
        lines.append(f'{value:016x}')

    with open(output_hex_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    return output_hex_path


def has_signature_symbols(symbols):
    """
    Check if the ELF has DifuzzRTL signature infrastructure symbols.
    Returns True only if ALL required symbols exist, not just a partial set.

    This prevents sending partially-instrumented ELFs down the "already wrapped"
    path, which would cause KeyError later in RTL input/signature parsing.
    """
    # Core signature symbols
    required_core = ['begin_signature', 'end_signature', 'tohost']

    # GPR output symbols (all 32)
    required_gprs = [f'reg_x{i}_output' for i in range(32)]

    # FPR output symbols (all 32)
    required_fprs = [f'reg_f{i}_output' for i in range(32)]

    # CSR output symbols (all CSR names used by sigChecker)
    csr_names = [
        'fflags', 'frm', 'fcsr', 'sstatus', 'sie', 'sscratch', 'sepc', 'scause',
        'stval', 'sip', 'satp', 'mhartid', 'mstatus', 'medeleg', 'mie', 'mscratch',
        'mepc', 'mcause', 'mtval', 'mip', 'pmpcfg0', 'pmpaddr0', 'pmpaddr1',
        'pmpaddr2', 'pmpaddr3', 'pmpaddr4', 'pmpaddr5', 'pmpaddr6', 'pmpaddr7'
    ]
    required_csrs = [f'{name}_output' for name in csr_names]

    # Random data sections
    required_data = [f'_random_data{i}' for i in range(6)]
    required_data_end = [f'_end_data{i}' for i in range(6)]

    # End marker (used by sigChecker.read_symbols)
    required_end = ['_end_main']

    # Combine all required symbols
    all_required = (required_core + required_gprs + required_fprs +
                     required_csrs + required_data + required_data_end + required_end)

    # Check if all required symbols exist
    missing = [sym for sym in all_required if sym not in symbols]
    if missing:
        # Don't print all missing symbols in production, just return False
        # But for debugging, we can log what's missing
        import sys
        if '--debug' in sys.argv or any(sym in symbols for sym in required_core[:3]):
            # Only show missing if we already have some signature symbols
            # (partial instrumentation case)
            pass  # Could log: f"Missing signature symbols: {missing[:5]}...")
        return False

    return True


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


def get_text_section_end(elf_path):
    """
    Get the actual end address of ALL .text* sections from an ELF file.

    This uses readelf to parse the section headers and find ALL sections whose
    names start with '.text' (e.g., .text, .text.init, .text.startup).
    Returns the maximum end address (max(vaddr + size)) across all text sections.

    This handles multi-section executables where code is split across
    .text.init, .text, and other .text.* sections.

    Args:
        elf_path: Path to the ELF file

    Returns:
        The maximum end address across all .text* sections (vaddr + size),
        or None if no text sections are found
    """
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
        return None

    max_end = None

    for line in result.stdout.split('\n'):
        # Check if this line contains a .text* section
        # We match sections that start with '.text' and are PROGBITS with ALLOC + EXECUTE flags
        if '.text' in line and 'PROGBITS' in line and ('AX' in line or 'XA' in line):
            # Format: [Nr] Name Type Addr Off Size ES Flg Lk Inf Al
            # Example: [ 1] .text.init PROGBITS 80000000 001000 00044c 00 AX 0 0 64
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # Find the address and size columns
                    addr_idx = None
                    size_idx = None
                    for i, p in enumerate(parts):
                        if 'PROGBITS' in p:
                            # Next non-header after PROGBITS is Addr
                            if i + 1 < len(parts):
                                addr_idx = i + 1
                            if i + 3 < len(parts):
                                size_idx = i + 3
                            break

                    if addr_idx is not None and size_idx is not None:
                        addr = int(parts[addr_idx], 16)
                        size = int(parts[size_idx], 16)
                        end = addr + size
                        if max_end is None or end > max_end:
                            max_end = end
                except (ValueError, IndexError):
                    continue

    return max_end


def get_data_sections_info(elf_path):
    """
    Get information about data sections (.data, .rodata, .sdata, etc.) from an ELF file.

    Returns a list of tuples (name, address, size) for each data section.

    Args:
        elf_path: Path to the ELF file

    Returns:
        List of (name, address, size) tuples, sorted by address
    """
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
        return []

    data_sections = []

    # GNU readelf -S can output section headers in multi-line format.
    # Merge continuation lines into a single line for easier parsing.
    # Multi-line example:
    #   [ 2] .data PROGBITS         00001450  001450
    #        00000000000002f0  00000000000002f0  WA  0   0 16
    # Single-line example:
    #   [ 2] .data PROGBITS 00001450 001450 0002f0 00 WA  0   0 16
    merged_lines = []
    for line in result.stdout.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # Check if this is a continuation line (starts with spaces/whitespace but no '[')
        # Continuation lines contain Addr, Off, Size, ES, Flg, Lk, Inf, Al values
        if stripped[0].isspace() and '[' not in stripped and merged_lines:
            # Append to previous line
            merged_lines[-1] = merged_lines[-1] + ' ' + stripped
        else:
            merged_lines.append(stripped)

    for line in merged_lines:
        # Check for data sections: .data*, .rodata*, .sdata*, .srodata*, etc.
        if 'PROGBITS' in line:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # Parse the section header format
                    # Format: [Nr] Name Type Addr Off Size ES Flg Lk Inf Al
                    # Example: [ 2] .data PROGBITS 00001450 001450 0002f0 00 WA  0   0 16
                    # After split(): ['[', '2]', '.data', 'PROGBITS', '00001450', '001450', '0002f0', ...]
                    # The first token is '[' and the second is 'N]' (index number with bracket)
                    # The actual section name comes after the index tokens

                    # Skip initial '[' and 'N]' tokens
                    idx = 0
                    while idx < len(parts) and (parts[idx] == '[' or parts[idx].endswith(']')):
                        idx += 1

                    if idx >= len(parts):
                        continue

                    section_name = parts[idx]

                    # Check if section name starts with data section prefixes
                    is_data_section = (
                        section_name.startswith('.data') or
                        section_name.startswith('.rodata') or
                        section_name.startswith('.sdata') or
                        section_name.startswith('.srodata')
                    )

                    if is_data_section:
                        # Find PROGBITS type column to get address and size offsets
                        addr_idx = None
                        size_idx = None
                        for i, p in enumerate(parts):
                            if p == 'PROGBITS':
                                if i + 1 < len(parts):
                                    addr_idx = i + 1
                                if i + 3 < len(parts):
                                    size_idx = i + 3
                                break

                        if addr_idx is not None and size_idx is not None:
                            addr = int(parts[addr_idx], 16)
                            size = int(parts[size_idx], 16)
                            if size > 0:  # Only include non-empty sections
                                data_sections.append((section_name, addr, size))
                except (ValueError, IndexError):
                    continue

    # Sort by address
    data_sections.sort(key=lambda x: x[1])
    return data_sections


def get_bss_sections_info(elf_path):
    """
    Get information about BSS sections (.bss, .sbss, etc.) from an ELF file.

    Returns a list of tuples (name, address, size) for each BSS section.

    Args:
        elf_path: Path to the ELF file

    Returns:
        List of (name, address, size) tuples, sorted by address
    """
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
        return []

    bss_sections = []

    # GNU readelf -S can output section headers in multi-line format.
    # Merge continuation lines into a single line for easier parsing.
    merged_lines = []
    for line in result.stdout.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # Check if this is a continuation line (starts with spaces/whitespace but no '[')
        if stripped[0].isspace() and '[' not in stripped and merged_lines:
            # Append to previous line
            merged_lines[-1] = merged_lines[-1] + ' ' + stripped
        else:
            merged_lines.append(stripped)

    for line in merged_lines:
        # Check for BSS sections: .bss*, .sbss*, etc.
        # These sections contain zero-initialized data and take up space in the ELF
        if 'NOBITS' in line:  # BSS sections use NOBITS instead of PROGBITS
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # Parse the section header format
                    # Skip '[' and 'N]' tokens to find the section name
                    idx = 0
                    while idx < len(parts) and (parts[idx] == '[' or parts[idx].endswith(']')):
                        idx += 1

                    if idx >= len(parts):
                        continue

                    section_name = parts[idx]

                    # Check if section name starts with BSS prefixes
                    is_bss_section = (
                        section_name.startswith('.bss') or
                        section_name.startswith('.sbss')
                    )

                    if is_bss_section:
                        # Find NOBITS type column to get address and size offsets
                        addr_idx = None
                        size_idx = None
                        for i, p in enumerate(parts):
                            if p == 'NOBITS':
                                if i + 1 < len(parts):
                                    addr_idx = i + 1
                                if i + 3 < len(parts):
                                    size_idx = i + 3
                                break

                        if addr_idx is not None and size_idx is not None:
                            addr = int(parts[addr_idx], 16)
                            size = int(parts[size_idx], 16)
                            if size > 0:  # Only include non-empty sections
                                bss_sections.append((section_name, addr, size))
                except (ValueError, IndexError):
                    continue

    # Sort by address
    bss_sections.sort(key=lambda x: x[1])
    return bss_sections


def detect_isa_from_binary(bin_path):
    """
    Detect ISA width (RV32 vs RV64) from a raw binary file.

    WARNING: This function uses a heuristic approach and may not be reliable
    for all binaries. For standalone .bin files, it is strongly recommended
    to provide an explicit ISA width hint via --isa-width parameter.

    Args:
        bin_path: Path to the .bin file

    Returns:
        'rv32' if the binary appears to be RV32, 'rv64' if RV64 or unknown

    Note:
        For reliable ISA detection, use the ELF file instead of .bin format,
        or explicitly specify the ISA width when calling resolve_bin_to_elf().
    """
    try:
        # Get actual file size, not just the read buffer size
        file_size = os.path.getsize(bin_path)

        # Read a larger sample to inspect instruction patterns
        with open(bin_path, 'rb') as f:
            # Read up to 8KB to get a better sample
            data = f.read(8192)

        if len(data) < 4:
            # Too small to analyze, default to rv64
            return 'rv64'

        # Heuristic 1: Check for RV64-specific instructions
        # Look for instructions that only exist in RV64:
        # - LWU (load word unsigned): 0x00002003 (base pattern)
        # - LD (load double): 0x00003003 (base pattern)
        # - SD (store double): 0x00003023 (base pattern)
        # These are simplified patterns - real detection needs disassembly
        rv64_hint_count = 0
        total_nonzero = 0

        for i in range(0, len(data) - 3, 4):
            instr = int.from_bytes(data[i:i+4], byteorder='little')
            if instr != 0:
                total_nonzero += 1
                # Check for potential RV64 load/store patterns
                # These are very basic heuristics
                opcode = instr & 0x7F
                # RV64 has additional load/store opcodes
                if opcode in [0x03, 0x23]:  # Load/Store base
                    # Check for width fields that suggest 64-bit
                    funct3 = (instr >> 12) & 0x7
                    if funct3 in [0x3, 0x4]:  # Double-word load/store hints
                        rv64_hint_count += 1

        # Heuristic 2: Use file size as a weak indicator
        # (this is NOT reliable, just a fallback)
        # Smaller test programs might be RV32, larger ones might be RV64
        # But this is easily wrong, so we weight it less

        # Decision: if we see clear RV64 hints, use rv64
        if total_nonzero > 0 and rv64_hint_count / total_nonzero > 0.05:
            return 'rv64'

        # Otherwise, use file size as a weak hint (but this is unreliable)
        # Default to rv64 for ambiguity since it's more common in modern systems
        if file_size > 16384:  # > 16KB suggests larger code, maybe RV64
            return 'rv64'
        else:
            # For smaller binaries, we can't reliably determine
            # Default to rv64 as the safer choice
            return 'rv64'

    except Exception:
        return 'rv64'  # Default on error


def resolve_bin_to_elf(bin_path, isa_width_hint=None):
    """
    Resolve a .bin file to its corresponding .elf file for corpus processing.

    For corpus .bin files that have a same-stem sibling .elf, this returns
    the sibling .elf path and extracts metadata from it. For standalone .bin files,
    this generates a minimal ELF.

    Args:
        bin_path: Path to the .bin file
        isa_width_hint: Optional ISA width hint ('rv32' or 'rv64') for standalone binaries

    Returns:
        Tuple of (elf_path, isa_width, symbols) where:
        - elf_path: Path to use for ELF processing (sibling .elf or generated)
        - isa_width: 'rv32' or 'rv64'
        - symbols: Symbol dictionary from the ELF
    """
    if not os.path.isfile(bin_path):
        raise FileNotFoundError(f"Binary file not found: {bin_path}")

    # Check for same-stem sibling .elf file
    bin_dir = os.path.dirname(bin_path)
    bin_basename = os.path.basename(bin_path)
    stem = os.path.splitext(bin_basename)[0]  # Remove .bin extension

    # Look for same-stem .elf file
    sibling_elf = os.path.join(bin_dir, stem + '.elf')

    if os.path.isfile(sibling_elf):
        # Use the sibling .elf file
        try:
            isa_width = get_elf_isa_width(sibling_elf)
            symbols = get_symbols(sibling_elf)
            return (sibling_elf, isa_width, symbols)
        except Exception as e:
            # If sibling .elf is invalid, fall through to generation
            pass

    # No valid sibling .elf found, generate a minimal ELF
    # For standalone .bin files, require explicit ISA width
    if not isa_width_hint:
        raise ValueError(
            f"Standalone .bin file requires explicit --isa-width parameter. "
            f"Please specify --isa-width rv32 or --isa-width rv64."
        )

    isa_width = isa_width_hint

    # Generate minimal ELF
    generated_elf = bin_to_elf(bin_path, output_elf_path=None, isa_width=isa_width)

    # Extract symbols from generated ELF
    symbols = get_symbols(generated_elf)

    return (generated_elf, isa_width, symbols)


def bin_to_elf(bin_path, output_elf_path=None, isa_width=None, entry_addr=DRAM_BASE, output_dir=None):
    """
    Convert a raw binary file (.bin) to a minimal RISC-V ELF file.

    This creates a minimal ELF wrapper around the binary data with:
    - .text section containing the binary code
    - Basic symbols (_start, _end_main, __bss_start, __bss_end)
    - Proper entry point

    Args:
        bin_path: Path to the input .bin file
        output_elf_path: Path for the output ELF file (default: same as input with .elf)
        isa_width: ISA width ('rv32' or 'rv64')
        entry_addr: Entry point address (default: DRAM_BASE)
        output_dir: Directory for output files (overrides output_elf_path directory)

    Returns:
        Path to the generated ELF file
    """
    if not os.path.isfile(bin_path):
        raise FileNotFoundError(f"Binary file not found: {bin_path}")

    if output_elf_path is None:
        if output_dir is not None:
            base = os.path.splitext(os.path.basename(bin_path))[0]
            output_elf_path = os.path.join(output_dir, base + '.elf')
        else:
            base = os.path.splitext(bin_path)[0]
            output_elf_path = base + '.elf'

    with open(bin_path, 'rb') as f:
        binary_data = f.read()

    # Select compiler flags based on ISA width
    if isa_width == 'rv32':
        march = '-march=rv32g'
        mabi = '-mabi=ilp32'
    else:
        march = '-march=rv64g'
        mabi = '-mabi=lp64'

    # Create a temporary assembly file that includes the binary data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.S', delete=False) as asm_file:
        asm_path = asm_file.name

        # Convert binary data to instruction directives
        # IMPORTANT: Do NOT pad to 4-byte alignment!
        # The original binary may end with a 16-bit compressed instruction,
        # and adding padding would insert extra zeros that get executed.
        # Use a mix of .word, .2byte, and .byte directives as needed.
        words = []
        i = 0
        while i < len(binary_data):
            if i + 4 <= len(binary_data):
                # Emit a 4-byte word
                word = struct.unpack_from('<I', binary_data, i)[0]
                words.append(f'    .word 0x{word:08x}')
                i += 4
            elif i + 2 <= len(binary_data):
                # Emit a 2-byte halfword (compressed instruction)
                halfword = struct.unpack_from('<H', binary_data, i)[0]
                words.append(f'    .2byte 0x{halfword:04x}')
                i += 2
            else:
                # Odd number of bytes - emit as single byte
                words.append(f'    .byte 0x{binary_data[i]:02x}')
                i += 1

        binary_code = '\n'.join(words)

        # Generate minimal ELF assembly with basic symbols
        asm_content = f'''# Auto-generated ELF wrapper for binary file
# Source: {os.path.basename(bin_path)}
# ISA Width: {isa_width}

.section .text.init
.align 6
.global _start
_start:
    # ---- Binary data from {os.path.basename(bin_path)} ----
{binary_code}
    # ---- End binary data ----

.global _end_main
_end_main:
    unimp

.global __bss_start
__bss_start:
    .skip 0

.global __bss_end
__bss_end:
    .skip 0
'''

        asm_file.write(asm_content)

    # Get link.ld path from template directory
    template_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'difuzz-rtl', 'Fuzzer', 'Template'
    )
    link_ld = os.path.join(template_dir, 'include', 'link.ld')

    # Compile to ELF
    cc = 'riscv64-unknown-elf-gcc'
    cc_args = [
        cc,
        march, mabi,
        '-static', '-mcmodel=medany',
        '-fvisibility=hidden',
        '-nostdlib', '-nostartfiles',
        '-T', link_ld,
        '-Wl,--defsym=_start={:#x}'.format(entry_addr),
        asm_path,
        '-o', output_elf_path
    ]

    ret = subprocess.run(cc_args, capture_output=True, text=True)
    if ret.returncode != 0:
        # Clean up temp file
        os.unlink(asm_path)
        raise RuntimeError(
            f"Failed to compile binary to ELF:\n{ret.stderr}\nCommand: {' '.join(cc_args)}"
        )

    # Clean up temp file
    os.unlink(asm_path)

    return output_elf_path


def extract_data_sections(elf_path, max_sections=6):
    """
    Extract data sections from an ELF file for use in signature comparison.

    Uses objdump to extract .data, .rodata, and .sdata sections,
    returning them as a list of byte arrays suitable for the
    _random_data* regions used by DifuzzRTL's signature infrastructure.

    Args:
        elf_path: Path to the ELF file
        max_sections: Maximum number of data sections to extract (default: 6)

    Returns:
        List of (start_addr, end_addr, bytes) tuples, one per data section.
        Returns empty list if no data sections found or on error.
    """
    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    # Use objdump to get section information
    result = subprocess.run(
        ['riscv64-unknown-elf-objdump', '-h', elf_path],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        # Fallback to system objdump
        result = subprocess.run(
            ['objdump', '-h', elf_path],
            capture_output=True, text=True
        )

    if result.returncode != 0:
        # Can't extract sections, return empty
        return []

    # Parse section headers to find data sections
    data_sections = []
    for line in result.stdout.split('\n'):
        parts = line.split()
        if len(parts) < 6:
            continue

        section_name = parts[1]
        if section_name in ['.data', '.rodata', '.sdata', '.srodata']:
            try:
                size = int(parts[2], 16)
                if size > 0:
                    data_sections.append((section_name, size))
            except ValueError:
                continue

    if not data_sections:
        return []

    # Use objcopy to extract each data section
    extracted_data = []
    for i, (section_name, size) in enumerate(data_sections[:max_sections]):
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_file = os.path.join(tmpdir, f'section_{i}.bin')

            # Extract this specific section
            ret = subprocess.run(
                ['riscv64-unknown-elf-objcopy', '-O', 'binary',
                 '-j', section_name, elf_path, bin_file],
                capture_output=True
            )

            if ret.returncode != 0:
                # Try with system objcopy
                ret = subprocess.run(
                    ['objcopy', '-O', 'binary',
                     '-j', section_name, elf_path, bin_file],
                    capture_output=True
                )

            if ret.returncode == 0:
                with open(bin_file, 'rb') as f:
                    section_data = f.read()
                    # Align to 8 bytes
                    if len(section_data) % 8 != 0:
                        section_data += b'\x00' * (8 - len(section_data) % 8)
                    extracted_data.append(section_data)

    return extracted_data


def get_spike_memory_map(elf_path, symbols=None):
    """
    Derive Spike -m<a:m,...> memory map regions from an ELF file.

    Spike's -m flag format is -m<a:m,...> where:
    - Each region is <base>:<size>
    - Regions are 4 KiB aligned
    - Multiple regions can be specified separated by commas

    This function analyzes the ELF's PT_LOAD segments and derives the
    memory map regions needed for Spike to access all memory regions,
    including any low-address communication regions (tohost/fromhost).

    Args:
        elf_path: Path to the ELF file
        symbols: Optional symbol dictionary (if None, will call get_symbols())

    Returns:
        List of (base, size) tuples suitable for Spike's -m flag,
        or None if no special memory mapping is needed (all segments at DRAM_BASE)

    Example:
        >>> regions = get_spike_memory_map('progs/test.elf')
        >>> if regions:
        >>>     spike_args = ['-m' + ','.join([f'{base:x}:{size:x}' for base, size in regions])]
        >>>     # spike_args might be ['-m0x1000:0x1000,0x7000:0x1000']
    """
    if symbols is None:
        symbols = get_symbols(elf_path)

    if not os.path.isfile(elf_path):
        raise FileNotFoundError(f"ELF file not found: {elf_path}")

    # Get PT_LOAD segments from the ELF
    load_segments = []
    try:
        result = subprocess.run(
            ['riscv64-unknown-elf-readelf', '-l', elf_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            result = subprocess.run(
                ['readelf', '-l', elf_path],
                capture_output=True, text=True
            )
    except FileNotFoundError:
        raise RuntimeError("readelf not found")

    # Parse PT_LOAD segments
    # GNU readelf -l has two formats:
    # 1. Single-line: LOAD 0x001000 0x00001000 0x00001000 0x00788 0x00788 RWE 0x1000
    # 2. Multi-line:
    #    LOAD           0x0000000000001000 0x0000000000001000 0x0000000000001000
    #                   0x000000000000054c 0x000000000000054c  R E    0x1000
    pending_vaddr = None
    for line in result.stdout.split('\n'):
        stripped = line.strip()
        if stripped.startswith('LOAD'):
            # Try to parse single-line format first
            parts = stripped.split()
            if len(parts) >= 6:
                try:
                    # Check if we have all fields on one line (Offset, VirtAddr, PhysAddr, FileSiz, MemSiz)
                    # Index 1=Offset, 2=VirtAddr, 3=PhysAddr, 4=FileSiz, 5=MemSiz
                    vaddr = int(parts[2], 16)  # VirtAddr is at index 2
                    memsz = int(parts[5], 16)  # MemSiz is at index 5
                    load_segments.append((vaddr, memsz))
                    pending_vaddr = None
                    continue
                except (ValueError, IndexError):
                    # Single-line parse failed, might be multi-line format
                    try:
                        pending_vaddr = int(parts[2], 16)  # Store VirtAddr, wait for next line for MemSiz
                    except (ValueError, IndexError):
                        pending_vaddr = None
        elif pending_vaddr is not None and stripped:
            # Second line of multi-line format: contains FileSiz and MemSiz
            # Format: 0x000000000000054c 0x000000000000054c  R E    0x1000
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    memsz = int(parts[1], 16)  # MemSiz is at index 1 on second line
                    load_segments.append((pending_vaddr, memsz))
                    pending_vaddr = None
                except (ValueError, IndexError):
                    pending_vaddr = None
            else:
                pending_vaddr = None
        elif stripped and not stripped[0].isspace():
            # Not a continuation line, reset pending state
            pending_vaddr = None

    if not load_segments:
        return None  # No PT_LOAD segments found, use default mapping

    DRAM_BASE = 0x80000000

    # Build regions map, aligning to 4 KiB boundaries
    regions = []
    for vaddr, memsz in load_segments:
        # Align base down to 4 KiB
        base = vaddr & ~0xFFF
        # Calculate region size based on aligned segment end address
        # For vaddr=0x1004, memsz=0x1000: end=0x2004, aligned_end=0x3000, size=0x2000
        end = vaddr + memsz
        aligned_end = (end + 0xFFF) & ~0xFFF
        size = aligned_end - base

        # Check if this region is at DRAM_BASE or below
        if base >= DRAM_BASE:
            # Normal DRAM region - Spike handles this by default
            continue
        else:
            # Low-address region - needs explicit mapping
            # Merge with overlapping regions instead of dropping them
            new_end = base + size

            # Find all overlapping regions and merge them all
            merged_base = base
            merged_end = new_end
            indices_to_remove = []

            for i, (existing_base, existing_size) in enumerate(regions):
                existing_end = existing_base + existing_size

                # Check for overlap: intervals [base, new_end) and [existing_base, existing_end)
                if not (new_end <= existing_base or base >= existing_end):
                    # Overlap detected - expand merged region
                    merged_base = min(merged_base, existing_base)
                    merged_end = max(merged_end, existing_end)
                    indices_to_remove.append(i)

            # Remove overlapped regions (in reverse order to preserve indices)
            for i in reversed(indices_to_remove):
                del regions[i]

            # Add the merged region
            regions.append((merged_base, merged_end - merged_base))

    # Check for tohost/fromhost at low addresses
    tohost_addr = symbols.get('tohost', 0)
    fromhost_addr = symbols.get('fromhost', 0)

    for comm_addr in [tohost_addr, fromhost_addr]:
        if comm_addr and comm_addr < DRAM_BASE:
            # Align to 4 KiB
            base = comm_addr & ~0xFFF
            size = 0x1000  # 4 KiB region
            new_end = base + size

            # Find all overlapping regions and merge them all
            merged_base = base
            merged_end = new_end
            indices_to_remove = []

            for i, (existing_base, existing_size) in enumerate(regions):
                existing_end = existing_base + existing_size

                # Check for overlap
                if not (new_end <= existing_base or base >= existing_end):
                    # Overlap detected - expand merged region
                    merged_base = min(merged_base, existing_base)
                    merged_end = max(merged_end, existing_end)
                    indices_to_remove.append(i)

            # Remove overlapped regions (in reverse order to preserve indices)
            for i in reversed(indices_to_remove):
                del regions[i]

            # Add the merged region
            regions.append((merged_base, merged_end - merged_base))

    # Sort regions by base address
    regions.sort(key=lambda x: x[0])

    if not regions:
        return None  # No low-address regions found, use default mapping

    return regions
