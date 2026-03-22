"""
Wrapper generator: takes a bare RISC-V ELF/binary and wraps it with
the DifuzzRTL signature infrastructure (tohost, register dump,
begin_signature/end_signature) so it can be used for difftest.
"""

import os
import subprocess
import tempfile
import struct

from elf_utils import get_symbols, elf_to_memory_dict, DRAM_BASE


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
    """
    if output_asm_path is None:
        base = os.path.splitext(elf_path)[0]
        output_asm_path = base + '.wrapper.S'

    # Read the user's binary to extract instruction bytes
    memory = elf_to_memory_dict(elf_path)
    symbols = get_symbols(elf_path)

    start = symbols.get('_start', DRAM_BASE)
    end = symbols.get('__bss_start', symbols.get('__bss_end', start + 0x1000))

    # Collect raw bytes
    raw_bytes = bytearray()
    for addr in range(start, end):
        offset = addr - start
        word_addr = (addr // 8) * 8 + start
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

    # Generate the wrapper assembly
    asm = f"""# Auto-generated wrapper for difftest
# Source: {os.path.basename(elf_path)}

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
    sd x0,   0(t5)
    sd x1,   8(t5)
    sd x2,  16(t5)
    sd x3,  24(t5)
    sd x4,  32(t5)
    sd x5,  40(t5)
    sd x6,  48(t5)
    sd x7,  56(t5)
    sd x8,  64(t5)
    sd x9,  72(t5)
    sd x10, 80(t5)
    sd x11, 88(t5)
    sd x12, 96(t5)
    sd x13,104(t5)
    sd x14,112(t5)
    sd x15,120(t5)
    sd x16,128(t5)
    sd x17,136(t5)
    sd x18,144(t5)
    sd x19,152(t5)
    sd x20,160(t5)
    sd x21,168(t5)
    sd x22,176(t5)
    sd x23,184(t5)
    sd x24,192(t5)
    sd x25,200(t5)
    sd x26,208(t5)
    sd x27,216(t5)
    sd x28,224(t5)
    sd x29,232(t5)
    sd x30,240(t5)
    sd x31,248(t5)

    # Dump FP registers
    la t5, reg_f0_output
    fsd f0,   0(t5)
    fsd f1,   8(t5)
    fsd f2,  16(t5)
    fsd f3,  24(t5)
    fsd f4,  32(t5)
    fsd f5,  40(t5)
    fsd f6,  48(t5)
    fsd f7,  56(t5)
    fsd f8,  64(t5)
    fsd f9,  72(t5)
    fsd f10, 80(t5)
    fsd f11, 88(t5)
    fsd f12, 96(t5)
    fsd f13,104(t5)
    fsd f14,112(t5)
    fsd f15,120(t5)
    fsd f16,128(t5)
    fsd f17,136(t5)
    fsd f18,144(t5)
    fsd f19,152(t5)
    fsd f20,160(t5)
    fsd f21,168(t5)
    fsd f22,176(t5)
    fsd f23,184(t5)
    fsd f24,192(t5)
    fsd f25,200(t5)
    fsd f26,208(t5)
    fsd f27,216(t5)
    fsd f28,224(t5)
    fsd f29,232(t5)
    fsd f30,240(t5)
    fsd f31,248(t5)

    # Dump key CSRs
    la t5, fflags_output
    csrr t6, fflags;   sd t6, 0(t5)
    csrr t6, frm;      sd t6, 8(t5)
    csrr t6, fcsr;     sd t6, 16(t5)
    csrr t6, mstatus;  sd t6, 24(t5)
    csrr t6, mepc;     sd t6, 32(t5)
    csrr t6, mcause;   sd t6, 40(t5)
    csrr t6, mtval;    sd t6, 48(t5)

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
    fmv.d.x f0, t0
    fmv.d.x f1, t0
    fmv.d.x f2, t0
    fmv.d.x f3, t0
    fmv.d.x f4, t0
    fmv.d.x f5, t0
    fmv.d.x f6, t0
    fmv.d.x f7, t0
    fmv.d.x f8, t0
    fmv.d.x f9, t0
    fmv.d.x f10, t0
    fmv.d.x f11, t0
    fmv.d.x f12, t0
    fmv.d.x f13, t0
    fmv.d.x f14, t0
    fmv.d.x f15, t0
    fmv.d.x f16, t0
    fmv.d.x f17, t0
    fmv.d.x f18, t0
    fmv.d.x f19, t0
    fmv.d.x f20, t0
    fmv.d.x f21, t0
    fmv.d.x f22, t0
    fmv.d.x f23, t0
    fmv.d.x f24, t0
    fmv.d.x f25, t0
    fmv.d.x f26, t0
    fmv.d.x f27, t0
    fmv.d.x f28, t0
    fmv.d.x f29, t0
    fmv.d.x f30, t0
    fmv.d.x f31, t0

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

.align 8
xreg_output_data:
.global reg_x0_output
reg_x0_output:  .dword 0
reg_x1_output:  .dword 0
reg_x2_output:  .dword 0
reg_x3_output:  .dword 0
reg_x4_output:  .dword 0
reg_x5_output:  .dword 0
reg_x6_output:  .dword 0
reg_x7_output:  .dword 0
reg_x8_output:  .dword 0
reg_x9_output:  .dword 0
reg_x10_output: .dword 0
reg_x11_output: .dword 0
reg_x12_output: .dword 0
reg_x13_output: .dword 0
reg_x14_output: .dword 0
reg_x15_output: .dword 0
reg_x16_output: .dword 0
reg_x17_output: .dword 0
reg_x18_output: .dword 0
reg_x19_output: .dword 0
reg_x20_output: .dword 0
reg_x21_output: .dword 0
reg_x22_output: .dword 0
reg_x23_output: .dword 0
reg_x24_output: .dword 0
reg_x25_output: .dword 0
reg_x26_output: .dword 0
reg_x27_output: .dword 0
reg_x28_output: .dword 0
reg_x29_output: .dword 0
reg_x30_output: .dword 0
reg_x31_output: .dword 0

.align 8
freg_output_data:
reg_f0_output:  .dword 0
reg_f1_output:  .dword 0
reg_f2_output:  .dword 0
reg_f3_output:  .dword 0
reg_f4_output:  .dword 0
reg_f5_output:  .dword 0
reg_f6_output:  .dword 0
reg_f7_output:  .dword 0
reg_f8_output:  .dword 0
reg_f9_output:  .dword 0
reg_f10_output: .dword 0
reg_f11_output: .dword 0
reg_f12_output: .dword 0
reg_f13_output: .dword 0
reg_f14_output: .dword 0
reg_f15_output: .dword 0
reg_f16_output: .dword 0
reg_f17_output: .dword 0
reg_f18_output: .dword 0
reg_f19_output: .dword 0
reg_f20_output: .dword 0
reg_f21_output: .dword 0
reg_f22_output: .dword 0
reg_f23_output: .dword 0
reg_f24_output: .dword 0
reg_f25_output: .dword 0
reg_f26_output: .dword 0
reg_f27_output: .dword 0
reg_f28_output: .dword 0
reg_f29_output: .dword 0
reg_f30_output: .dword 0
reg_f31_output: .dword 0

.align 8
csr_output_data:
fflags_output:  .dword 0
frm_output:     .dword 0
fcsr_output:    .dword 0
sstatus_output: .dword 0
sie_output:     .dword 0
sscratch_output:.dword 0
sepc_output:    .dword 0
scause_output:  .dword 0
stval_output:   .dword 0
sip_output:     .dword 0
satp_output:    .dword 0
mhartid_output: .dword 0
mstatus_output: .dword 0
medeleg_output: .dword 0
mie_output:     .dword 0
mscratch_output:.dword 0
mepc_output:    .dword 0
mcause_output:  .dword 0
mtval_output:   .dword 0
mip_output:     .dword 0
pmpcfg0_output: .dword 0
pmpaddr0_output:.dword 0
pmpaddr1_output:.dword 0
pmpaddr2_output:.dword 0
pmpaddr3_output:.dword 0
pmpaddr4_output:.dword 0
pmpaddr5_output:.dword 0
pmpaddr6_output:.dword 0
pmpaddr7_output:.dword 0

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


def compile_wrapper(asm_path, output_elf_path=None, output_hex_path=None):
    """
    Compile the wrapper assembly into an ELF and hex file.
    Uses rv64g to match the DifuzzRTL Rocket/Boom target.
    """
    if output_elf_path is None:
        output_elf_path = os.path.splitext(asm_path)[0] + '.elf'
    if output_hex_path is None:
        output_hex_path = os.path.splitext(asm_path)[0] + '.hex'

    link_ld = os.path.join(TEMPLATE_DIR, 'include', 'link.ld')

    cc = 'riscv64-unknown-elf-gcc'
    cc_args = [
        cc,
        '-march=rv64g', '-mabi=lp64',
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
    compile_wrapper(asm_path, wrapped_elf, wrapped_hex)

    # Extract symbols from wrapped ELF
    symbols = get_symbols(wrapped_elf)

    return {
        'elf': wrapped_elf,
        'hex': wrapped_hex,
        'asm': asm_path,
        'symbols': symbols,
        'output_dir': output_dir,
    }
