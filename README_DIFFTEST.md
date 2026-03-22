# Difftest Tool for RISC-V ELF Files

A tool for running differential testing on RISC-V ELF binaries using Spike (ISA reference simulator) and optional RTL simulation comparison.

## Features

- **ELF Loading**: Load pre-compiled RISC-V ELF files from `progs/` directory
- **Symbol Extraction**: Extract symbol table using `riscv64-unknown-elf-nm`
- **ELF Wrapping**: Automatically wrap bare ELFs with DifuzzRTL signature infrastructure
- **Spike Execution**: Run ELF files through Spike ISA simulator
- **Signature Comparison**: Compare ISA and RTL execution signatures
- **Batch Processing**: Process multiple ELF files in parallel

## Requirements

- Python 3.6+
- RISC-V toolchain (`riscv64-unknown-elf-gcc`, `riscv64-unknown-elf-nm`)
- Spike ISA simulator (built in `difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/build/spike` or in PATH)

## Installation

No installation required. The tool uses Python standard library and subprocess to call external tools.

## Usage

### Single File Mode

```bash
python run_difftest.py --elf progs/test.elf
```

### Batch Mode

```bash
python run_difftest.py --progs-dir progs/ --pattern "*.elf"
```

### With RTL Signature Comparison

```bash
python run_difftest.py --elf progs/test.elf --rtl-sig rtl_signature.txt
```

### Options

- `--elf <path>`: Path to a single ELF file
- `--progs-dir <dir>`: Directory containing ELF files
- `--pattern <glob>`: Glob pattern for ELF files (default: *.elf)
- `--output-dir <dir>`: Output directory for wrapped files and signatures
- `--timeout <seconds>`: Spike timeout in seconds (default: 30)
- `--rtl-sig <path>`: Pre-generated RTL signature file for comparison
- `--debug`: Enable verbose debug output

## Output

The tool produces:
- Wrapped ELF files with signature infrastructure
- Spike ISA signature files
- Comparison results (PASS/MISMATCH)

### Exit Codes
- 0: All tests passed
- 1: One or more tests failed or errored

## How It Works

1. **ELF Analysis**: The tool reads the ELF file and extracts symbols
2. **Wrapping**: If the ELF lacks signature symbols, it wraps the binary with DifuzzRTL infrastructure (trap handler, register dump regions, tohost)
3. **Spike Execution**: Spike runs the wrapped ELF and generates a signature file
4. **Comparison**: If an RTL signature is provided, the tool compares ISA and RTL signatures

## Module Overview

- `elf_utils.py`: ELF loading and symbol extraction utilities
- `elf_wrapper.py`: Wraps bare ELFs with signature infrastructure
- `spike_runner.py`: Spike execution wrapper
- `signature_compare.py`: Signature comparison logic
- `run_difftest.py`: Main entry script

## RTL Simulation

RTL simulation requires the cocotb/Verilator environment from DifuzzRTL. For standalone use:

1. Generate RTL signatures separately using the full DifuzzRTL cocotb testbench
2. Use `--rtl-sig` to compare against pre-generated RTL signatures

## Example

```bash
# Run single test
python run_difftest.py --elf progs/rv32d_addi_x0_x0_0x0_Retire_Success.elf --debug

# Batch process all rv32d tests
python run_difftest.py --progs-dir progs/ --pattern "rv32d_*.elf"

# Compare with RTL signature
python run_difftest.py --elf progs/test.elf --rtl-sig test_rtl_sig.txt
```

## Limitations

- RTL simulation requires cocotb/Verilator environment (not included in standalone mode)
- Wrapper compilation requires RISC-V GCC toolchain
- Only supports RV64G ISA (can be customized in code)

## License

This tool is part of the DifuzzRTL project.
