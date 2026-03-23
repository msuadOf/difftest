# ILL_MEM CLI test fixture
# Compact ELF with all DiffuzzRTL symbols at low address (0x1000)
# This triggers ILL_MEM in RTL while Spike runs with -m flag

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
    # Save x30, then dump all registers
    mv t6, t5
    la t5, reg_x0_output
    sw x1, 0(t5); sw x0, 4(t5)
    sw x2, 8(t5); sw x0, 12(t5)
    sw x3, 16(t5); sw x0, 20(t5)
    sw x4, 24(t5); sw x0, 28(t5)
    sw x5, 32(t5); sw x0, 36(t5)
    sw x6, 40(t5); sw x0, 44(t5)
    sw x7, 48(t5); sw x0, 52(t5)
    sw x8, 56(t5); sw x0, 60(t5)
    sw x9, 64(t5); sw x0, 68(t5)
    sw x10, 72(t5); sw x0, 76(t5)
    sw x11, 80(t5); sw x0, 84(t5)
    sw x12, 88(t5); sw x0, 92(t5)
    sw x13, 96(t5); sw x0, 100(t5)
    sw x14, 104(t5); sw x0, 108(t5)
    sw x15, 112(t5); sw x0, 116(t5)
    sw x16, 120(t5); sw x0, 124(t5)
    sw x17, 128(t5); sw x0, 132(t5)
    sw x18, 136(t5); sw x0, 140(t5)
    sw x19, 144(t5); sw x0, 148(t5)
    sw x20, 152(t5); sw x0, 156(t5)
    sw x21, 160(t5); sw x0, 164(t5)
    sw x22, 168(t5); sw x0, 172(t5)
    sw x23, 176(t5); sw x0, 180(t5)
    sw x24, 184(t5); sw x0, 188(t5)
    sw x25, 192(t5); sw x0, 196(t5)
    sw x26, 200(t5); sw x0, 204(t5)
    sw x27, 208(t5); sw x0, 212(t5)
    sw x28, 216(t5); sw x0, 220(t5)
    sw x29, 224(t5); sw x0, 228(t5)
    # x30 from t6
    sw t6, 232(t5); sw x0, 236(t5)
    sw x31, 240(t5); sw x0, 244(t5)

    # Dump FP registers
    la t5, reg_f0_output
    fsd f0, 0(t5); fsd f1, 8(t5)
    fsd f2, 16(t5); fsd f3, 24(t5)
    fsd f4, 32(t5); fsd f5, 40(t5)
    fsd f6, 48(t5); fsd f7, 56(t5)
    fsd f8, 64(t5); fsd f9, 72(t5)
    fsd f10, 80(t5); fsd f11, 88(t5)
    fsd f12, 96(t5); fsd f13, 104(t5)
    fsd f14, 112(t5); fsd f15, 120(t5)
    fsd f16, 128(t5); fsd f17, 136(t5)
    fsd f18, 144(t5); fsd f19, 152(t5)
    fsd f20, 160(t5); fsd f21, 168(t5)
    fsd f22, 176(t5); fsd f23, 184(t5)
    fsd f24, 192(t5); fsd f25, 200(t5)
    fsd f26, 208(t5); fsd f27, 216(t5)
    fsd f28, 224(t5); fsd f29, 232(t5)
    fsd f30, 240(t5); fsd f31, 248(t5)

    # Dump CSRs
    la t5, fflags_output
    csrr t6, fflags; sw t6, 0(t5); sw x0, 4(t5)
    csrr t6, frm; sw t6, 8(t5); sw x0, 12(t5)
    csrr t6, fcsr; sw t6, 16(t5); sw x0, 20(t5)
    csrr t6, sstatus; sw t6, 24(t5); sw x0, 28(t5)
    csrr t6, sie; sw t6, 32(t5); sw x0, 36(t5)
    csrr t6, sscratch; sw t6, 40(t5); sw x0, 44(t5)
    csrr t6, sepc; sw t6, 48(t5); sw x0, 52(t5)
    csrr t6, scause; sw t6, 56(t5); sw x0, 60(t5)
    csrr t6, stval; sw t6, 64(t5); sw x0, 68(t5)
    csrr t6, sip; sw t6, 72(t5); sw x0, 76(t5)
    csrr t6, satp; sw t6, 80(t5); sw x0, 84(t5)
    csrr t6, mhartid; sw t6, 88(t5); sw x0, 92(t5)
    csrr t6, mstatus; sw t6, 96(t5); sw x0, 100(t5)
    csrr t6, medeleg; sw t6, 104(t5); sw x0, 108(t5)
    csrr t6, mie; sw t6, 112(t5); sw x0, 116(t5)
    csrr t6, mscratch; sw t6, 120(t5); sw x0, 124(t5)
    csrr t6, mepc; sw t6, 128(t5); sw x0, 132(t5)
    csrr t6, mcause; sw t6, 136(t5); sw x0, 140(t5)
    csrr t6, mtval; sw t6, 144(t5); sw x0, 148(t5)
    csrr t6, mip; sw t6, 152(t5); sw x0, 156(t5)
    csrr t6, pmpcfg0; sw t6, 160(t5); sw x0, 164(t5)
    csrr t6, pmpaddr0; sw t6, 168(t5); sw x0, 172(t5)
    csrr t6, pmpaddr1; sw t6, 176(t5); sw x0, 180(t5)
    csrr t6, pmpaddr2; sw t6, 184(t5); sw x0, 188(t5)
    csrr t6, pmpaddr3; sw t6, 192(t5); sw x0, 196(t5)
    csrr t6, pmpaddr4; sw t6, 200(t5); sw x0, 204(t5)
    csrr t6, pmpaddr5; sw t6, 208(t5); sw x0, 212(t5)
    csrr t6, pmpaddr6; sw t6, 216(t5); sw x0, 220(t5)
    csrr t6, pmpaddr7; sw t6, 224(t5); sw x0, 228(t5)

    # Write to tohost
    li t5, 1
    la t6, tohost
    sw t5, 0(t6)
_test_end:
    j _test_end

reset_vector:
    csrwi mstatus, 0
    la t0, trap_handler
    csrw mtvec, t0
    li t0, 0x6000
    csrs mstatus, t0
    csrwi fcsr, 0
    li t0, 0
    fcvt.d.w f0, t0; fcvt.d.w f1, t0; fcvt.d.w f2, t0
    fcvt.d.w f3, t0; fcvt.d.w f4, t0; fcvt.d.w f5, t0
    fcvt.d.w f6, t0; fcvt.d.w f7, t0; fcvt.d.w f8, t0
    fcvt.d.w f9, t0; fcvt.d.w f10, t0; fcvt.d.w f11, t0
    fcvt.d.w f12, t0; fcvt.d.w f13, t0; fcvt.d.w f14, t0
    fcvt.d.w f15, t0; fcvt.d.w f16, t0; fcvt.d.w f17, t0
    fcvt.d.w f18, t0; fcvt.d.w f19, t0; fcvt.d.w f20, t0
    fcvt.d.w f21, t0; fcvt.d.w f22, t0; fcvt.d.w f23, t0
    fcvt.d.w f24, t0; fcvt.d.w f25, t0; fcvt.d.w f26, t0
    fcvt.d.w f27, t0; fcvt.d.w f28, t0; fcvt.d.w f29, t0
    fcvt.d.w f30, t0; fcvt.d.w f31, t0
    li x1, 0; li x2, 0; li x3, 0; li x4, 0
    li x5, 0; li x6, 0; li x7, 0; li x8, 0
    li x9, 0; li x10, 0; li x11, 0; li x12, 0
    li x13, 0; li x14, 0; li x15, 0; li x16, 0
    li x17, 0; li x18, 0; li x19, 0; li x20, 0
    li x21, 0; li x22, 0; li x23, 0; li x24, 0
    li x25, 0; li x26, 0; li x27, 0; li x28, 0
    li x29, 0; li x30, 0; li x31, 0
    la t0, user_code
    csrw mepc, t0
    li t0, 0
    mret

.align 6
user_code:
    addi x1, x0, 1
    addi x2, x0, 2
    ecall
    unimp
_end_main:
    unimp

.data

# tohost/fromhost at separate low address region (0x7000)
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

.align 3
# xreg output (32 registers * 8 bytes each = 256 bytes)
.global reg_x0_output
xreg_output_data:
reg_x0_output: .dword 0
reg_x1_output: .dword 0
reg_x2_output: .dword 0
reg_x3_output: .dword 0
reg_x4_output: .dword 0
reg_x5_output: .dword 0
reg_x6_output: .dword 0
reg_x7_output: .dword 0
reg_x8_output: .dword 0
reg_x9_output: .dword 0
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

.align 3
# freg output (32 registers * 8 bytes each = 256 bytes)
.global reg_f0_output
freg_output_data:
reg_f0_output: .dword 0
reg_f1_output: .dword 0
reg_f2_output: .dword 0
reg_f3_output: .dword 0
reg_f4_output: .dword 0
reg_f5_output: .dword 0
reg_f6_output: .dword 0
reg_f7_output: .dword 0
reg_f8_output: .dword 0
reg_f9_output: .dword 0
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

.align 3
# csr output (29 registers * 8 bytes each = 232 bytes)
.global fflags_output
fflags_output: .dword 0
.global frm_output
frm_output: .dword 0
.global fcsr_output
fcsr_output: .dword 0
.global sstatus_output
sstatus_output: .dword 0
.global sie_output
sie_output: .dword 0
.global sscratch_output
sscratch_output: .dword 0
.global sepc_output
sepc_output: .dword 0
.global scause_output
scause_output: .dword 0
.global stval_output
stval_output: .dword 0
.global sip_output
sip_output: .dword 0
.global satp_output
satp_output: .dword 0
.global mhartid_output
mhartid_output: .dword 0
.global mstatus_output
mstatus_output: .dword 0
.global medeleg_output
medeleg_output: .dword 0
.global mie_output
mie_output: .dword 0
.global mscratch_output
mscratch_output: .dword 0
.global mepc_output
mepc_output: .dword 0
.global mcause_output
mcause_output: .dword 0
.global mtval_output
mtval_output: .dword 0
.global mip_output
mip_output: .dword 0
.global pmpcfg0_output
pmpcfg0_output: .dword 0
.global pmpaddr0_output
pmpaddr0_output: .dword 0
.global pmpaddr1_output
pmpaddr1_output: .dword 0
.global pmpaddr2_output
pmpaddr2_output: .dword 0
.global pmpaddr3_output
pmpaddr3_output: .dword 0
.global pmpaddr4_output
pmpaddr4_output: .dword 0
.global pmpaddr5_output
pmpaddr5_output: .dword 0
.global pmpaddr6_output
pmpaddr6_output: .dword 0
.global pmpaddr7_output
pmpaddr7_output: .dword 0

.align 4
.global end_signature
end_signature:

# Random data sections
.align 3
.global _random_data0
_random_data0:
.global _end_data0
_end_data0:
.align 3
.global _random_data1
_random_data1:
.global _end_data1
_end_data1:
.align 3
.global _random_data2
_random_data2:
.global _end_data2
_end_data2:
.align 3
.global _random_data3
_random_data3:
.global _end_data3
_end_data3:
.align 3
.global _random_data4
_random_data4:
.global _end_data4
_end_data4:
.align 3
.global _random_data5
_random_data5:
.global _end_data5
_end_data5:
