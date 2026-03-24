"""
Standalone signature comparison module for difftest.
Provides comparison between ISA (Spike) and RTL signatures without
requiring the full DifuzzRTL framework.
"""

import os


# Register names for output
XREG_NAMES = ('zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 's1',
              'a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 's2', 's3',
              's4', 's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4',
              't5', 't6')

FREG_NAMES = ('ft0', 'ft1', 'ft2', 'ft3', 'ft4', 'ft5', 'ft6', 'ft7',
              'fs0', 'fs1', 'fa0', 'fa1', 'fa2', 'fa3', 'fa4', 'fa5',
              'fa6', 'fa7', 'fs2', 'fs3', 'fs4', 'fs5', 'fs6', 'fs7',
              'fs8', 'fs9', 'fs10', 'fs11', 'ft8', 'ft9', 'ft10', 'ft11')

CSR_NAMES = ('fflags', 'frm', 'fcsr',
             'sstatus', 'sie', 'sscratch', 'sepc', 'scause', 'stval', 'sip', 'satp',
             'mhartid', 'mstatus', 'medeleg', 'mie', 'mscratch', 'mepc', 'mcause', 'mtval', 'mip',
             'pmpcfg0', 'pmpaddr0', 'pmpaddr1', 'pmpaddr2', 'pmpaddr3', 'pmpaddr4',
             'pmpaddr5', 'pmpaddr6', 'pmpaddr7')


class SignatureComparer:
    """Compare ISA and RTL execution signatures."""

    def __init__(self, symbols, debug=False):
        """
        Initialize comparer with symbol addresses.

        Args:
            symbols: Dict mapping symbol names to addresses (from get_symbols())
            debug: Enable verbose output
        """
        self.symbols = symbols
        self.debug = debug

        # Verify required symbols exist
        required = ['begin_signature', 'end_signature']
        for sym in required:
            if sym not in symbols:
                raise ValueError(f"Missing required symbol: {sym}")

    def _read_signature_file(self, sig_file):
        """Read signature file into list of 32-bit values.

        DifuzzRTL signature format: each line is 32 characters (128 bits)
        containing 4 x 32-bit values in a specific layout.
        We extract each 32-bit value in the correct order.
        """
        if not os.path.isfile(sig_file):
            raise FileNotFoundError(f"Signature file not found: {sig_file}")

        values = []
        with open(sig_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Each line is 32 characters (128 bits) containing 4 x 32-bit values
                # Format according to DifuzzRTL's read_sig():
                # lines[idx // 2][16 - 16 * (idx % 2):32 - 16 * (idx % 2)]
                # This means:
                # - idx 0: line[16:32]   (2nd 32-bit chunk)
                # - idx 1: line[0:16]    (1st 32-bit chunk)
                # - idx 2: line[48:64]   (4th 32-bit chunk, if line was longer)
                # - idx 3: line[32:48]   (3rd 32-bit chunk, if line was longer)
                # But since each line is exactly 32 chars:
                # - idx 0: line[16:32]
                # - idx 1: line[0:16]
                # For the next slot (idx 2,3), they would be on the next line
                if len(line) == 32:
                    # First 32-bit value (chars 16-31)
                    values.append(int(line[16:32], 16))
                    # Second 32-bit value (chars 0-15)
                    values.append(int(line[0:16], 16))

        return values

    def _get_signature_region(self, sig_values):
        """Extract the signature region from signature values."""
        sig_start = self.symbols['begin_signature']
        sig_end = self.symbols['end_signature']

        # Calculate offset in 32-bit values (each signature slot is 8 bytes with one 32-bit value)
        region_size = sig_end - sig_start
        num_slots = region_size // 8

        return sig_values[:num_slots]  # Each slot is one 32-bit value

    def compare(self, isa_sig_file, rtl_sig_file=None):
        """
        Compare ISA signature with optional RTL signature.

        Args:
            isa_sig_file: Path to ISA (Spike) signature file
            rtl_sig_file: Path to RTL signature file (optional)

        Returns:
            dict with:
                - 'match': True if signatures match (or RTL not provided)
                - 'isa_only': True if no RTL signature provided
                - 'mismatches': List of mismatch details
                - 'xreg_mismatches': Count of x register mismatches
                - 'freg_mismatches': Count of f register mismatches
                - 'csr_mismatches': Count of CSR mismatches
        """
        result = {
            'match': True,
            'isa_only': rtl_sig_file is None,
            'mismatches': [],
            'xreg_mismatches': 0,
            'freg_mismatches': 0,
            'csr_mismatches': 0,
            'data_mismatches': 0,
        }

        # Read ISA signature
        try:
            isa_values = self._read_signature_file(isa_sig_file)
        except Exception as e:
            result['match'] = False
            result['mismatches'].append(f"Failed to read ISA signature: {e}")
            return result

        # If no RTL signature, just validate ISA signature format
        if rtl_sig_file is None:
            if self.debug:
                print(f"[SignatureCompare] ISA signature loaded: {len(isa_values)} values")
            return result

        # Read RTL signature
        try:
            rtl_values = self._read_signature_file(rtl_sig_file)
        except Exception as e:
            result['match'] = False
            result['mismatches'].append(f"Failed to read RTL signature: {e}")
            return result

        # Compare signature regions
        if len(isa_values) != len(rtl_values):
            result['match'] = False
            result['mismatches'].append(
                f"Signature size mismatch: ISA={len(isa_values)}, RTL={len(rtl_values)}"
            )
            return result

        # Compare registers if output symbols exist
        if 'reg_x0_output' in self.symbols:
            result.update(self._compare_registers(isa_values, rtl_values))

        if 'reg_f0_output' in self.symbols:
            freg_result = self._compare_fp_registers(isa_values, rtl_values)
            result['freg_mismatches'] += freg_result['freg_mismatches']
            result['mismatches'].extend(freg_result['mismatches'])

        if result['xreg_mismatches'] > 0 or result['freg_mismatches'] > 0:
            result['match'] = False

        # Compare CSRs if symbols exist
        csr_result = self._compare_csrs(isa_values, rtl_values)
        result['csr_mismatches'] = csr_result['csr_mismatches']
        result['mismatches'].extend(csr_result['mismatches'])

        if result['csr_mismatches'] > 0:
            result['match'] = False

        # Compare _random_data* sections if symbols exist
        data_result = self._compare_data_sections(isa_values, rtl_values)
        result['data_mismatches'] = data_result['data_mismatches']
        result['mismatches'].extend(data_result['mismatches'])

        if result['data_mismatches'] > 0:
            result['match'] = False

        return result

    def _compare_registers(self, isa_values, rtl_values):
        """Compare integer registers."""
        sig_start = self.symbols['begin_signature']
        reg_x0_base = self.symbols['reg_x0_output']

        mismatches = []
        xreg_mismatches = 0

        # Each register is stored as a single 32-bit value in the signature
        for i in range(32):
            sym_name = f'reg_x{i}_output'
            if sym_name not in self.symbols:
                continue

            # Each signature slot is 8 bytes, containing one 32-bit value
            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset  # Direct index, each slot is one 32-bit value

            if idx >= len(isa_values) or idx >= len(rtl_values):
                continue

            isa_val = isa_values[idx]
            rtl_val = rtl_values[idx]

            if isa_val != rtl_val:
                xreg_mismatches += 1
                mismatch = f"x{i} ({XREG_NAMES[i]}): ISA=0x{isa_val:016x}, RTL=0x{rtl_val:016x}"
                mismatches.append(mismatch)
                if self.debug:
                    print(f"[SignatureCompare] MISMATCH: {mismatch}")

        return {
            'xreg_mismatches': xreg_mismatches,
            'mismatches': mismatches,
        }

    def _compare_fp_registers(self, isa_values, rtl_values):
        """Compare floating-point registers."""
        sig_start = self.symbols['begin_signature']

        mismatches = []
        freg_mismatches = 0

        # Each FP register is stored as a single 32-bit value in the signature
        for i in range(32):
            sym_name = f'reg_f{i}_output'
            if sym_name not in self.symbols:
                continue

            # Each signature slot is 8 bytes, containing one 32-bit value
            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset  # Direct index, each slot is one 32-bit value

            if idx >= len(isa_values) or idx >= len(rtl_values):
                continue

            isa_val = isa_values[idx]
            rtl_val = rtl_values[idx]

            if isa_val != rtl_val:
                freg_mismatches += 1
                mismatch = f"f{i} ({FREG_NAMES[i]}): ISA=0x{isa_val:016x}, RTL=0x{rtl_val:016x}"
                mismatches.append(mismatch)

        return {
            'freg_mismatches': freg_mismatches,
            'mismatches': mismatches,
        }

    def _compare_csrs(self, isa_values, rtl_values):
        """Compare control and status registers."""
        sig_start = self.symbols['begin_signature']

        mismatches = []
        csr_mismatches = 0

        # Each CSR is stored as a single 32-bit value in the signature
        for csr_name in CSR_NAMES:
            sym_name = f'{csr_name}_output'
            if sym_name not in self.symbols:
                continue

            # Each signature slot is 8 bytes, containing one 32-bit value
            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset  # Direct index, each slot is one 32-bit value

            if idx >= len(isa_values) or idx >= len(rtl_values):
                continue

            isa_val = isa_values[idx]
            rtl_val = rtl_values[idx]

            if isa_val != rtl_val:
                csr_mismatches += 1
                mismatch = f"{csr_name}: ISA=0x{isa_val:016x}, RTL=0x{rtl_val:016x}"
                mismatches.append(mismatch)

        return {
            'csr_mismatches': csr_mismatches,
            'mismatches': mismatches,
        }

    def _compare_data_sections(self, isa_values, rtl_values):
        """Compare _random_data* sections."""
        sig_start = self.symbols['begin_signature']

        mismatches = []
        data_mismatches = 0

        # Compare up to 6 _random_data sections
        for i in range(6):
            data_start_sym = f'_random_data{i}'
            data_end_sym = f'_end_data{i}'

            if data_start_sym not in self.symbols or data_end_sym not in self.symbols:
                continue

            data_start = self.symbols[data_start_sym]
            data_end = self.symbols[data_end_sym]

            # Calculate offset and size
            offset = (data_start - sig_start) // 8
            size_bytes = data_end - data_start
            size_words = size_bytes // 8

            # Check bounds
            if offset + size_words > len(isa_values) or offset + size_words > len(rtl_values):
                continue

            # Compare each 64-bit word
            section_mismatches = 0
            for j in range(size_words):
                idx = offset + j
                isa_val = isa_values[idx]
                rtl_val = rtl_values[idx]

                if isa_val != rtl_val:
                    section_mismatches += 1
                    addr = data_start + 8 * j
                    mismatches.append(
                        f"data{i}[+0x{j*2:x}]: ISA=0x{isa_val:016x}, RTL=0x{rtl_val:016x} @ 0x{addr:x}"
                    )

            if section_mismatches > 0:
                data_mismatches += section_mismatches
                if self.debug:
                    print(f"  _random_data{i}: {section_mismatches}/{size_words} words mismatch")

        return {
            'data_mismatches': data_mismatches,
            'mismatches': mismatches,
        }

    def print_report(self, result):
        """Print a human-readable comparison report."""
        if result['isa_only']:
            print("  Signature: ISA signature validated (no RTL signature provided for comparison)")
            return

        if result['match']:
            print("  Signature: PASS - All registers match")
        else:
            print("  Signature: MISMATCH")
            print(f"    X register mismatches: {result['xreg_mismatches']}")
            print(f"    F register mismatches: {result['freg_mismatches']}")
            print(f"    CSR mismatches: {result['csr_mismatches']}")
            print(f"    Data section mismatches: {result['data_mismatches']}")

            if self.debug and result['mismatches']:
                print("  Detailed mismatches:")
                for m in result['mismatches'][:20]:  # Limit output
                    print(f"    - {m}")
                if len(result['mismatches']) > 20:
                    print(f"    ... and {len(result['mismatches']) - 20} more")


def compare_signatures(isa_sig_file, rtl_sig_file, symbols, debug=False):
    """
    Convenience function to compare two signature files.

    Args:
        isa_sig_file: Path to ISA signature file
        rtl_sig_file: Path to RTL signature file (or None)
        symbols: Dict of symbol addresses
        debug: Enable verbose output

    Returns:
        Same as SignatureComparer.compare()
    """
    comparer = SignatureComparer(symbols, debug=debug)
    return comparer.compare(isa_sig_file, rtl_sig_file)
