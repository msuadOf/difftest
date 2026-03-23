# Test program that triggers ILL_MEM
# This program has code at address 0x1000 (below DRAM_BASE, not in bootrom)
# which should trigger ILL_MEM detection in RTL simulation

.section .text
.global _start
_start:
    # Simple program
    addi x1, x0, 1
    addi x2, x0, 2

    # Write to tohost to terminate
    lui t5, %hi(tohost)
    addi t5, t5, %lo(tohost)
    li t6, 1
    sw t6, 0(t5)

    # Infinite loop
loop:
    j loop

.section .tohost,"aw",@progbits
.align 3
.global tohost
tohost: .dword 0
