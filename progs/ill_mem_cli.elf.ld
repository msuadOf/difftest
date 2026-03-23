/* Linker script for ILL_MEM CLI test fixture
 * All sections placed compactly below DRAM_BASE (0x80000000)
 * to trigger ILL_MEM in RTL while Spike executes with -m flag
 */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
    /* Low memory region - triggers ILL_MEM in RTL */
    LOW_MEM (rwx) : ORIGIN = 0x1000, LENGTH = 128K
}

SECTIONS
{
    /* Code starts at 0x1000 */
    .text.init : {
        *(.text.init)
    } > LOW_MEM

    .text : {
        *(.text .text.*)
    } > LOW_MEM

    /* Data sections immediately follow code */
    .data : {
        *(.data .data.*)
    } > LOW_MEM

    /* tohost/fromhost at fixed address 0x7000 */
    .tohost : {
        KEEP(*(.tohost))
    } > LOW_MEM

    /* Signature data */
    .signature : {
        *(begin_signature)
        *(xreg_output_data)
        *(freg_output_data)
        *(fflags_output)
        *(frm_output)
        *(fcsr_output)
        *(sstatus_output)
        *(sie_output)
        *(sscratch_output)
        *(sepc_output)
        *(scause_output)
        *(stval_output)
        *(sip_output)
        *(satp_output)
        *(mhartid_output)
        *(mstatus_output)
        *(medeleg_output)
        *(mie_output)
        *(mscratch_output)
        *(mepc_output)
        *(mcause_output)
        *(mtval_output)
        *(mip_output)
        *(pmpcfg0_output)
        *(pmpaddr0_output)
        *(pmpaddr1_output)
        *(pmpaddr2_output)
        *(pmpaddr3_output)
        *(pmpaddr4_output)
        *(pmpaddr5_output)
        *(pmpaddr6_output)
        *(pmpaddr7_output)
        *(end_signature)
    } > LOW_MEM

    /* Random data sections */
    .random_data : {
        *(_random_data0)
        *(_end_data0)
        *(_random_data1)
        *(_end_data1)
        *(_random_data2)
        *(_end_data2)
        *(_random_data3)
        *(_end_data3)
        *(_random_data4)
        *(_end_data4)
        *(_random_data5)
        *(_end_data5)
    } > LOW_MEM

    /* BSS */
    .bss : {
        *(.sbss .sbss.*)
        *(.bss .bss.*)
        *(COMMON)
    } > LOW_MEM

    /* Discard unwind info */
    /DISCARD/ : {
        *(.comment .note .note.* .debug_*)
    }
}
