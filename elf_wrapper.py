"""
Wrapper generator: takes a bare RISC-V ELF/binary and wraps it with
the DifuzzRTL signature infrastructure (tohost, register dump,
begin_signature/end_signature) so it can be used for difftest.
"""

import os
import subprocess
import tempfile
import struct

from elf_utils import get_symbols, elf_to_memory_dict, DRAM_BASE, get_elf_isa_width


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
    end = symbols.get('__bss_start', symbols.get('__bss_end', start + 0x1000))

    # Collect raw bytes
    raw_bytes = bytearray()
    for addr in range(start, end):
        # Calculate the 8-byte aligned address for this byte
        word_addr = addr & ~0x7  # Clear lowest 3 bits to align to 8 bytes
        if word_addr in memory:
            word = memory[word_addr]
            byte_offset = addr - word_addr
            raw_bytes.append((word >> (byte_offset * 8)) & 0xFF)
        else:
            raw_bytes.append(0)

    # Generate .word directives from raw bytes (aligned to 4 bytes)
    if len(raw_bytes) % 4 != 0:
        raw_bytes.extend(b'\x00' * (4 - len(raw_bytes) % 4))

    word_directives = []
    for i in range(0, len(raw_bytes), 4):
        w = struct.unpack_from('<I', raw_bytes, i)[0]
        word_directives.append(f'    .word 0x{w:08x}')

    user_code = '\n'.join(word_directives)

    # Choose store instructions based on ISA width
    if is_rv32:
        xreg_store = 'sw'   # 32-bit store for RV32
        freg_store = 'fsw'  # 32-bit FP store for RV32 (RV32 only has 32-bit FP regs)
        csr_store = 'sw'    # 32-bit store for CSRs
        reg_size = 4        # 4 bytes per register
        fp_move = 'fmv.w.x' # FP move instruction for RV32
    else:
        xreg_store = 'sd'   # 64-bit store for RV64
        freg_store = 'fsd'  # 64-bit FP store for RV64
        csr_store = 'sd'    # 64-bit store for CSRs
        reg_size = 8        # 8 bytes per register
        fp_move = 'fmv.d.x' # FP move instruction for RV64

    # Generate register store instructions
    xreg_stores = []
    for i in range(32):
        offset = i * reg_size
        xreg_stores.append(f'    {xreg_store} x{i},{offset}(t5)')

    freg_stores = []
    for i in range(32):
        offset = i * reg_size
        freg_stores.append(f'    {freg_store} f{i},{offset}(t5)')

    csr_stores = []
    csr_names = ['fflags', 'frm', 'fcsr', 'sstatus', 'sie', 'sscratch', 'sepc',
                 'scause', 'stval', 'sip', 'satp', 'mhartid', 'mstatus',
                 'medeleg', 'mie', 'mscratch', 'mepc', 'mcause', 'mtval', 'mip',
                 'pmpcfg0', 'pmpaddr0', 'pmpaddr1', 'pmpaddr2', 'pmpaddr3',
                 'pmpaddr4', 'pmpaddr5', 'pmpaddr6', 'pmpaddr7']
    for i, csr_name in enumerate(csr_names):
        offset = i * reg_size
        csr_stores.append(f'    csrr t6, {csr_name}; {csr_store} t6,{offset}(t5)')

    # Generate FP register initialization instructions
    fp_init = []
    for i in range(32):
        fp_init.append(f'    {fp_move} f{i}, t0')

    xreg_store_code = '\n'.join(xreg_stores)
    freg_store_code = '\n'.join(freg_stores)
    csr_store_code = '\n'.join(csr_stores)
    fp_init_code = '\n'.join(fp_init)

    # Generate data section directives
    data_directive = '.word' if is_rv32 else '.dword'
    align_directive = '.align 2' if is_rv32 else '.align 3'  # 4-byte or 8-byte align

    # Generate xreg output data
    xreg_data = []
    xreg_data.append(f'{align_directive}')
    xreg_data.append('xreg_output_data:')
    for i in range(32):
        xreg_data.append(f'.global reg_x{i}_output')
        xreg_data.append(f'reg_x{i}_output:  {data_directive} 0')

    # Generate freg output data
    freg_data = []
    freg_data.append(f'{align_directive}')
    freg_data.append('freg_output_data:')
    for i in range(32):
        freg_data.append(f'reg_f{i}_output:  {data_directive} 0')

    # Generate CSR output data
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
    # Dump all general-purpose registers to signature region
    la t5, reg_x0_output
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

    # Enable FP: set mstatus.FS = 01 (Initial)
    # mstatus.FS is bits [14:13], value 01 = 0x2000
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

# Empty random data sections (required by signature_checker)
.align 8
.global _random_data0
_random_data0:
.global _end_data0
_end_data0:

.align 8
.global _random_data1
_random_data1:
.global _end_data1
_end_data1:

.align 8
.global _random_data2
_random_data2:
.global _end_data2
_end_data2:

.align 8
.global _random_data3
_random_data3:
.global _end_data3
_end_data3:

.align 8
.global _random_data4
_random_data4:
.global _end_data4
_end_data4:

.align 8
.global _random_data5
_random_data5:
.global _end_data5
_end_data5:
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
    if isa_width == 'rv32':
        march = '-march=rv32g'
        mabi = '-mabi=ilp32'
    else:
        march = '-march=rv64g'
        mabi = '-mabi=lp64'

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

    # Generate flat hex for RTL simulation
    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, 'output.bin')
        subprocess.run(
            ['riscv64-unknown-elf-objcopy', output_elf_path, '-O', 'binary', bin_path],
            check=True, capture_output=True
        )
        with open(bin_path, 'rb') as f:
            data = f.read()

    if len(data) % 8 != 0:
        data += b'\x00' * (8 - len(data) % 8)

    with open(output_hex_path, 'w') as f:
        for i in range(0, len(data), 8):
            word = struct.unpack_from('<Q', data, i)[0]
            f.write(f'{word:016x}\n')

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
