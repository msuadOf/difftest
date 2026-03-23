/* Linker script for ILL_MEM test - places code at low address */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
    LOWmem (rwx) : ORIGIN = 0x1000, LENGTH = 0x1000
    TOHOST (rw)  : ORIGIN = 0x7000, LENGTH = 0x1000
}

SECTIONS
{
    .text : {
        *(.text.init)
        *(.text*)
    } > LOWmem

    .tohost : {
        . = ALIGN(8);
        tohost = .;
        *(.tohost)
    } > TOHOST

    /* Discard other sections */
    /DISCARD/ : {
        *(.data*)
        *(.rodata*)
        *(.bss*)
        *(.comment*)
    }
}
