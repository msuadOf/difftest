# RTL Simulation Integration Guide

## Current Status

The difftest tool currently supports:
- ✅ ELF loading and symbol extraction
- ✅ Spike ISA simulation
- ✅ Signature comparison (when both ISA and RTL signatures are available)
- ✅ Wrapper generation for ELFs lacking signature infrastructure
- ✅ RV32 and RV64 support

## RTL Simulation Requirements

The RTL simulation path requires the full cocotb/Verilator environment from DifuzzRTL. This includes:

1. **Verilated RTL Design**: The RISC-V processor design compiled with Verilator
2. **Cocotb Testbench**: The Python testbench that drives the simulation
3. **Memory Model**: TileLink adapter for memory access

## Running Full Difftest (with RTL)

### Prerequisites

1. Build the RTL design with Verilator:
```bash
cd difuzz-rtl/Fuzzer/RTLSim
# Follow build instructions in the DifuzzRTL project
```

2. Ensure cocotb is installed and the RTL design is compiled

### Option 1: Pre-generated RTL Signatures

For testing without the full cocotb environment, you can use pre-generated RTL signatures:

```bash
# Generate ISA signature first
python run_difftest.py --elf progs/test.elf --output-dir output/

# Then compare with pre-generated RTL signature
python run_difftest.py --elf progs/test.elf \
    --rtl-sig path/to/rtl_signature.txt \
    --output-dir output/
```

### Option 2: Full Cocotb Integration

To run the full end-to-end difftest with cocotb, you would need to:

1. Modify the RTL testbench (`RTLSim/host.py`) to accept command-line arguments
2. Create a driver script that:
   - Loads the wrapped ELF
   - Generates hex file from the ELF
   - Invokes cocotb with the appropriate parameters
   - Collects the RTL signature

This integration is complex and requires:
- Understanding the DifuzzRTL RTL infrastructure
- Setting up the cocotb environment
- Compiling the RTL design with Verilator

## Architecture Notes

The current implementation uses a **wrapper approach**:
1. Bare ELF files are wrapped with DifuzzRTL signature infrastructure
2. The wrapper includes:
   - Trap handler for register dump
   - Signature output regions
   - tohost signal for termination
3. This allows existing ELFs to work with DifuzzRTL's signature checking

### Memory Layout

The wrapper loads code at `DRAM_BASE` (0x80000000) and expects:
- Signature output at `begin_signature` (typically 0x80002000)
- tohost signal at a fixed address
- Register dump regions for x0-x31, f0-f31, and CSRs

### Limitations

1. **Binary (.bin) files**: Not currently supported because they lack symbol tables needed for wrapper generation
2. **RTL simulation**: Requires full cocotb/Verilator environment setup
3. **Interrupt testing**: Not implemented in the current wrapper

## Future Work

To complete the RTL simulation integration:

1. **Simplified RTL Runner**: Create a minimal RTL simulation runner that doesn't require the full cocotb setup
2. **Direct Binary Support**: Add support for raw .bin files with minimal symbol assumptions
3. **Automated Cocotb Integration**: Create a script that automates the cocotb invocation
