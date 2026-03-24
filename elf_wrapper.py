"""
Wrapper generator: takes a bare RISC-V ELF/binary and wraps it with
the DifuzzRTL signature infrastructure (tohost, register dump,
begin_signature/end_signature) so it can be used for difftest.
"""

import os
import subprocess
import tempfile
import struct

from elf_utils import get_symbols, elf_to_memory_dict, memory_dict_to_rtl_hex, DRAM_BASE, get_elf_isa_width, extract_data_sections, get_text_section_end


# Path to the DifuzzRTL template includes
TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'difuzz-rtl', 'Fuzzer', 'Template'
)


def extract_instructions_from_elf(elf_path):
    """
    Extract the raw instruction bytes from an ELF's .text section.
    Returns list of (address, instruction_word) tuples.
    """
    memory = elf_to_memory_dict(elf_path)
    symbols = get_symbols(elf_path)

    start = symbols.get('_start', DRAM_BASE)
    end = symbols.get('__bss_start', symbols.get('__bss_end', start + 0x1000))

    # Extract 32-bit instruction words
    instructions = []
    sorted_addrs = sorted(memory.keys())
    for addr in sorted_addrs:
        if addr < start or addr >= end:
            continue
        word = memory[addr]
        # Each 64-bit word contains two 32-bit halves
        low = word & 0xFFFFFFFF
        high = (word >> 32) & 0xFFFFFFFF
        instructions.append((addr, low))
        instructions.append((addr + 4, high))

    return instructions


def generate_wrapper_asm(elf_path, output_asm_path=None):
    """
    Generate a wrapper assembly file that includes the user's binary code
    within the DifuzzRTL template framework for proper difftest.

    The wrapper:
    1. Initializes registers and CSRs (including mstatus.FS for FP)
    2. Sets up trap handler that dumps all registers
    3. Executes the user's instructions
    4. Triggers ecall to dump state
    5. Writes to tohost to terminate

    Note: For RV32 binaries, uses 32-bit stores; for RV64, uses 64-bit stores.
    """
    if output_asm_path is None:
        base = os.path.splitext(elf_path)[0]
        output_asm_path = base + '.wrapper.S'

    # Detect ISA width
    isa_width = 'rv64'  # default
    try:
        isa_width = get_elf_isa_width(elf_path)
    except Exception as e:
        # If detection fails, use default
        pass

    is_rv32 = (isa_width == 'rv32')

    # Read the user's binary to extract instruction bytes
    memory = elf_to_memory_dict(elf_path)
    symbols = get_symbols(elf_path)

    start = symbols.get('_start', DRAM_BASE)

    # Determine where user code ends
    # Priority: _end_main symbol > actual code content > .text section end
    # _end_main is preferred because it marks the actual end of user code,
    # excluding any alignment padding that may be at the end of .text section
    if '_end_main' in symbols:
        code_end = symbols['_end_main']
    elif memory:
        # Scan memory to find the last non-zero instruction
        # This handles cases where _end_main doesn't exist but we have code
        max_addr = max(addr for addr in memory.keys() if addr >= start and addr < start + 0x100000)
        code_end = max_addr + 8
    else:
        # Last resort: use .text section end (may include padding)
        text_end = get_text_section_end(elf_path)
        if text_end is not None:
            code_end = text_end
        else:
            code_end = start + 0x1000

    # Collect code bytes (up to code_end, which is the actual .text section end)
    # This excludes .data, .rodata, and .bss sections
    raw_bytes = bytearray()
    for addr in range(start, code_end):
        # Calculate the 8-byte aligned address for this byte
        word_addr = addr & ~0x7  # Clear lowest 3 bits to align to 8 bytes
        if word_addr in memory:
            word = memory[word_addr]
            byte_offset = addr - word_addr
            raw_bytes.append((word >> (byte_offset * 8)) & 0xFF)
        else:
            raw_bytes.append(0)

    # Generate instruction directives from raw bytes
    # IMPORTANT: Do NOT pad to 4-byte alignment!
    # The original code may end with a 16-bit compressed instruction,
    # and adding padding would insert extra zeros that get executed.
    # Instead, emit a mix of .word and .2byte directives as needed.
    word_directives = []
    i = 0
    while i < len(raw_bytes):
        if i + 4 <= len(raw_bytes):
            # Emit a 4-byte word
            w = struct.unpack_from('<I', raw_bytes, i)[0]
            word_directives.append(f'    .word 0x{w:08x}')
            i += 4
        elif i + 2 <= len(raw_bytes):
            # Emit a 2-byte halfword (compressed instruction)
            h = struct.unpack_from('<H', raw_bytes, i)[0]
            word_directives.append(f'    .2byte 0x{h:04x}')
            i += 2
        else:
            # Odd number of bytes - should not happen in valid RISC-V code
            # Emit as single byte (not a standard instruction, but preserves data)
            word_directives.append(f'    .byte 0x{raw_bytes[i]:02x}')
            i += 1

    user_code = '\n'.join(word_directives)

    # Extract data sections from original ELF to populate _random_data regions
    # Note: We do NOT preserve original data section addresses in the wrapper
    # because .org uses absolute addresses which don't work correctly in
    # relocatable sections. For DifuzzRTL's use case (testing simple instruction
    # sequences), this is acceptable. If testing programs with data sections
    # is needed, the approach would be to use the original ELF directly without
    # wrapping, or to modify the linker script.
    data_sections = extract_data_sections(elf_path, max_sections=6)

    # Generate data section assembly code
    random_data_sections = []
    for i in range(6):
        section_name = f'_random_data{i}'
        end_name = f'_end_data{i}'

        if i < len(data_sections) and len(data_sections[i]) > 0:
            # Convert binary data to .dword directives
            section_data = data_sections[i]
            data_words = []
            for j in range(0, len(section_data), 8):
                if j + 8 <= len(section_data):
                    word = struct.unpack_from('<Q', section_data, j)[0]
                    data_words.append(f'    .dword 0x{word:016x}')

            data_code = '\n'.join(data_words)
            random_data_sections.append(f'''.align 8
.global {section_name}
{section_name}:
{data_code}
.global {end_name}
{end_name}:
''')
        else:
            # Empty section
            random_data_sections.append(f'''.align 8
.global {section_name}
{section_name}:
.global {end_name}
{end_name}:
''')

    random_data_code = '\n'.join(random_data_sections)

    # IMPORTANT: Signature regions must be 8-byte aligned for signature_checker.py
    # regardless of ISA width. For RV32, we use pairs of 32-bit stores per 8-byte slot.
    #
    # The compilation flags (-march/-mabi) still vary by ISA width.

    # FP initialization: use different instructions for RV32 vs RV64
    # RV32D has 64-bit FP registers but 32-bit integer registers
    # Use fcvt.d.w for RV32 to get proper full-width zero (converts int to double)
    # RV64 has 64-bit integer and FP registers, so use fmv.d.x
    if is_rv32:
        fp_move = 'fcvt.d.w'  # Convert 32-bit integer to 64-bit double (full-width init)
    else:
        fp_move = 'fmv.d.x'  # Move 64-bit integer to FP register

    # Generate register store instructions
    # CRITICAL: The template saves x30 to t6 before loading t5 with dump pointer
    # So t6 contains x30's original value when we reach xreg_store_code

    if is_rv32:
        # For RV32: use pairs of 32-bit stores to fill 8-byte aligned slots
        xreg_stores = []
        for i in range(32):
            offset = i * 8
            if i == 30:
                # x30: use saved value from t6
                xreg_stores.append(f'    sw t6,{offset}(t5)')
                xreg_stores.append(f'    sw x0,{offset+4}(t5)')  # Zero upper half
            else:
                # Store lower 32 bits, then upper 32 bits (which is 0 for our use case)
                xreg_stores.append(f'    sw x{i},{offset}(t5)')
                xreg_stores.append(f'    sw x0,{offset+4}(t5)')  # Zero upper half

        freg_stores = []
        for i in range(32):
            offset = i * 8
            # Use fsd for 64-bit FP registers (RV32D has 64-bit FP regs)
            # signature_checker.py expects 64-bit values regardless of ISA width
            freg_stores.append(f'    fsd f{i},{offset}(t5)')

        csr_stores = []
        csr_names = ['fflags', 'frm', 'fcsr', 'sstatus', 'sie', 'sscratch', 'sepc',
                     'scause', 'stval', 'sip', 'satp', 'mhartid', 'mstatus',
                     'medeleg', 'mie', 'mscratch', 'mepc', 'mcause', 'mtval', 'mip',
                     'pmpcfg0', 'pmpaddr0', 'pmpaddr1', 'pmpaddr2', 'pmpaddr3',
                     'pmpaddr4', 'pmpaddr5', 'pmpaddr6', 'pmpaddr7']
        for i, csr_name in enumerate(csr_names):
            offset = i * 8
            csr_stores.append(f'    csrr t6, {csr_name}; sw t6,{offset}(t5)')
            csr_stores.append(f'    sw x0,{offset+4}(t5)')  # Zero upper half
    else:
        # For RV64: use single 64-bit stores
        xreg_stores = []
        for i in range(32):
            offset = i * 8
            if i == 30:
                # x30: use saved value from t6
                xreg_stores.append(f'    sd t6,{offset}(t5)')
            else:
                xreg_stores.append(f'    sd x{i},{offset}(t5)')

        freg_stores = []
        for i in range(32):
            offset = i * 8
            freg_stores.append(f'    fsd f{i},{offset}(t5)')

        csr_stores = []
        csr_names = ['fflags', 'frm', 'fcsr', 'sstatus', 'sie', 'sscratch', 'sepc',
                     'scause', 'stval', 'sip', 'satp', 'mhartid', 'mstatus',
                     'medeleg', 'mie', 'mscratch', 'mepc', 'mcause', 'mtval', 'mip',
                     'pmpcfg0', 'pmpaddr0', 'pmpaddr1', 'pmpaddr2', 'pmpaddr3',
                     'pmpaddr4', 'pmpaddr5', 'pmpaddr6', 'pmpaddr7']
        for i, csr_name in enumerate(csr_names):
            offset = i * 8
            csr_stores.append(f'    csrr t6, {csr_name}; sd t6,{offset}(t5)')

    # Generate FP register initialization instructions
    fp_init = []
    for i in range(32):
        fp_init.append(f'    {fp_move} f{i}, t0')

    xreg_store_code = '\n'.join(xreg_stores)
    freg_store_code = '\n'.join(freg_stores)
    csr_store_code = '\n'.join(csr_stores)
    fp_init_code = '\n'.join(fp_init)

    # Generate data section directives (always 8-byte aligned for compatibility)
    # signature_checker.py expects 8-byte alignment regardless of ISA width
    data_directive = '.dword'  # Always use 8-byte (.dword/.quad) for signature compatibility
    align_directive = '.align 3'  # 8-byte align

    # Generate xreg output data (always 8-byte aligned)
    xreg_data = []
    xreg_data.append(f'{align_directive}')
    xreg_data.append('xreg_output_data:')
    for i in range(32):
        xreg_data.append(f'.global reg_x{i}_output')
        xreg_data.append(f'reg_x{i}_output:  {data_directive} 0')

    # Generate freg output data (always 8-byte aligned)
    freg_data = []
    freg_data.append(f'{align_directive}')
    freg_data.append('freg_output_data:')
    for i in range(32):
        freg_data.append(f'reg_f{i}_output:  {data_directive} 0')

    # Generate CSR output data (always 8-byte aligned)
    csr_data = []
    csr_data.append(f'{align_directive}')
    csr_data.append('csr_output_data:')
    for csr_name in csr_names:
        csr_data.append(f'{csr_name}_output:  {data_directive} 0')

    xreg_data_code = '\n'.join(xreg_data)
    freg_data_code = '\n'.join(freg_data)
    csr_data_code = '\n'.join(csr_data)

    # Generate the wrapper assembly
    asm = f"""# Auto-generated wrapper for difftest
# Source: {os.path.basename(elf_path)}
# ISA Width: {isa_width}

.section .text.init
.align 6
.global _start
_start:
    # Initialize all x registers to 0
    li x1, 0
    li x2, 0
    li x3, 0
    li x4, 0
    li x5, 0
    li x6, 0
    li x7, 0
    li x8, 0
    li x9, 0
    li x10, 0
    li x11, 0
    li x12, 0
    li x13, 0
    li x14, 0
    li x15, 0
    li x16, 0
    li x17, 0
    li x18, 0
    li x19, 0
    li x20, 0
    li x21, 0
    li x22, 0
    li x23, 0
    li x24, 0
    li x25, 0
    li x26, 0
    li x27, 0
    li x28, 0
    li x29, 0
    li x30, 0
    li x31, 0
    j reset_vector

.align 4
trap_handler:
    # CRITICAL: Save x30 (t5) before using it as base pointer for register dump
    # x30's value will be restored and stored separately
    mv t6, t5              # Save x30's current value to t6
    la t5, reg_x0_output   # Load dump pointer base address
{xreg_store_code}

    # Dump FP registers
    la t5, reg_f0_output
{freg_store_code}

    # Dump key CSRs
    la t5, fflags_output
{csr_store_code}

    # Write to tohost to signal completion
write_tohost:
    li t5, 1
    la t6, tohost
    sw t5, 0(t6)
_test_end:
    j _test_end

reset_vector:
    # Clear mstatus
    csrwi mstatus, 0

    # Set up trap handler
    la t0, trap_handler
    csrw mtvec, t0

    # Enable FP: set mstatus.FS = 11 (Dirty)
    # mstatus.FS is bits [14:13], value 11 = 0x6000
    li t0, 0x6000
    csrs mstatus, t0

    # Clear fcsr
    csrwi fcsr, 0

    # Initialize all FP registers to 0
    li t0, 0
{fp_init_code}

    # Re-initialize x registers
    li x1, 0
    li x2, 0
    li x3, 0
    li x4, 0
    li x5, 0
    li x6, 0
    li x7, 0
    li x8, 0
    li x9, 0
    li x10, 0
    li x11, 0
    li x12, 0
    li x13, 0
    li x14, 0
    li x15, 0
    li x16, 0
    li x17, 0
    li x18, 0
    li x19, 0
    li x20, 0
    li x21, 0
    li x22, 0
    li x23, 0
    li x24, 0
    li x25, 0
    li x26, 0
    li x27, 0
    li x28, 0
    li x29, 0
    li x30, 0
    li x31, 0

    # Set mepc to user_code and mret to it
    la t0, user_code
    csrw mepc, t0
    li t0, 0
    mret

.align 6
user_code:
    # ---- User instructions from {os.path.basename(elf_path)} ----
{user_code}
    # ---- End user instructions ----
    ecall
    unimp
_end_main:
    unimp
    unimp
    unimp
    unimp

.data

# tohost/fromhost for spike communication
.pushsection .tohost,"aw",@progbits
.align 6
.global tohost
tohost: .dword 0
.align 6
.global fromhost
fromhost: .dword 0
.popsection

.align 4
.global begin_signature
begin_signature:

{xreg_data_code}

{freg_data_code}

{csr_data_code}

.align 4
.global end_signature
end_signature:

# Data sections for signature comparison
# Populated from original ELF's .data, .rodata sections
{random_data_code}
"""

    with open(output_asm_path, 'w') as f:
        f.write(asm)

    return output_asm_path


def compile_wrapper(asm_path, original_elf_path=None, output_elf_path=None, output_hex_path=None):
    """
    Compile the wrapper assembly into an ELF and hex file.
    Detects ISA width from original ELF to use correct compiler flags.

    Args:
        asm_path: Path to the wrapper assembly file
        original_elf_path: Path to the original ELF (for ISA detection)
        output_elf_path: Path for output ELF
        output_hex_path: Path for output hex file
    """
    if output_elf_path is None:
        output_elf_path = os.path.splitext(asm_path)[0] + '.elf'
    if output_hex_path is None:
        output_hex_path = os.path.splitext(asm_path)[0] + '.hex'

    link_ld = os.path.join(TEMPLATE_DIR, 'include', 'link.ld')

    # Detect ISA width from original ELF
    isa_width = 'rv64'  # default
    if original_elf_path:
        try:
            isa_width = get_elf_isa_width(original_elf_path)
        except Exception as e:
            # If detection fails, use default
            pass

    # Select compiler flags based on ISA width
    # For RV32: use ilp32 ABI with g extension (includes f for single-precision FP)
    # For RV64: use lp64 ABI with g extension (includes f for single-precision FP)
    # Note: We use fmv.w.x for FP init in RV32, which works with F extension
    if isa_width == 'rv32':
        march = '-march=rv32imafdc'  # Include I M A F D C extensions for RV32
        mabi = '-mabi=ilp32'         # ilp32 ABI for RV32
    else:
        march = '-march=rv64imafdc'  # Include I M A F D C extensions for RV64
        mabi = '-mabi=lp64'          # lp64 ABI for RV64

    cc = 'riscv64-unknown-elf-gcc'
    cc_args = [
        cc,
        march, mabi,
        '-static', '-mcmodel=medany',
        '-fvisibility=hidden',
        '-nostdlib', '-nostartfiles',
        '-T', link_ld,
        asm_path,
        '-o', output_elf_path
    ]

    ret = subprocess.run(cc_args, capture_output=True, text=True)
    if ret.returncode != 0:
        raise RuntimeError(
            f"Compilation failed:\n{ret.stderr}\nCommand: {' '.join(cc_args)}"
        )

    # Generate segment-accurate hex for RTL simulation
    # This uses elf_to_memory_dict() to preserve actual segment addresses
    # instead of objcopy's flat binary approach
    memory = elf_to_memory_dict(output_elf_path)
    symbols = get_symbols(output_elf_path)
    memory_dict_to_rtl_hex(memory, symbols, output_hex_path)

    return output_elf_path, output_hex_path


def wrap_elf_for_difftest(elf_path, output_dir=None):
    """
    Full pipeline: take a bare ELF, wrap it with signature infrastructure,
    compile, and return paths to the wrapped ELF, hex, and symbol dict.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix='difftest_')

    base_name = os.path.splitext(os.path.basename(elf_path))[0]
    asm_path = os.path.join(output_dir, base_name + '.wrapper.S')
    wrapped_elf = os.path.join(output_dir, base_name + '.wrapped.elf')
    wrapped_hex = os.path.join(output_dir, base_name + '.wrapped.hex')

    # Generate wrapper assembly
    generate_wrapper_asm(elf_path, asm_path)

    # Compile
    compile_wrapper(asm_path, elf_path, wrapped_elf, wrapped_hex)

    # Extract symbols from wrapped ELF
    symbols = get_symbols(wrapped_elf)

    return {
        'elf': wrapped_elf,
        'hex': wrapped_hex,
        'asm': asm_path,
        'symbols': symbols,
        'output_dir': output_dir,
    }
