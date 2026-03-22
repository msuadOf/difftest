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
        """Read signature file into list of 64-bit values."""
        if not os.path.isfile(sig_file):
            raise FileNotFoundError(f"Signature file not found: {sig_file}")

        values = []
        with open(sig_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Each line contains two 32-bit hex values (16 chars each)
                # Format: {high32}{low32}
                if len(line) == 32:
                    low = int(line[16:32], 16)
                    high = int(line[0:16], 16)
                    values.append(low)
                    values.append(high)
                elif len(line) == 16:
                    values.append(int(line, 16))

        return values

    def _get_signature_region(self, sig_values):
        """Extract the signature region from signature values."""
        sig_start = self.symbols['begin_signature']
        sig_end = self.symbols['end_signature']

        # Calculate offset in 64-bit words
        region_size = sig_end - sig_start
        num_words = region_size // 8

        return sig_values[:num_words * 2]  # 2 values per line (low, high)

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

        return result

    def _compare_registers(self, isa_values, rtl_values):
        """Compare integer registers."""
        sig_start = self.symbols['begin_signature']
        reg_x0_base = self.symbols['reg_x0_output']

        mismatches = []
        xreg_mismatches = 0

        # Each register is 8 bytes, stored as two 32-bit values
        for i in range(32):
            sym_name = f'reg_x{i}_output'
            if sym_name not in self.symbols:
                continue

            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset * 2  # Two 32-bit values per 64-bit register

            if idx + 1 >= len(isa_values) or idx + 1 >= len(rtl_values):
                continue

            isa_val = (isa_values[idx + 1] << 32) | isa_values[idx]
            rtl_val = (rtl_values[idx + 1] << 32) | rtl_values[idx]

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

        for i in range(32):
            sym_name = f'reg_f{i}_output'
            if sym_name not in self.symbols:
                continue

            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset * 2

            if idx + 1 >= len(isa_values) or idx + 1 >= len(rtl_values):
                continue

            isa_val = (isa_values[idx + 1] << 32) | isa_values[idx]
            rtl_val = (rtl_values[idx + 1] << 32) | rtl_values[idx]

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

        for csr_name in CSR_NAMES:
            sym_name = f'{csr_name}_output'
            if sym_name not in self.symbols:
                continue

            offset = (self.symbols[sym_name] - sig_start) // 8
            idx = offset * 2

            if idx + 1 >= len(isa_values) or idx + 1 >= len(rtl_values):
                continue

            isa_val = (isa_values[idx + 1] << 32) | isa_values[idx]
            rtl_val = (rtl_values[idx + 1] << 32) | rtl_values[idx]

            if isa_val != rtl_val:
                csr_mismatches += 1
                mismatch = f"{csr_name}: ISA=0x{isa_val:016x}, RTL=0x{rtl_val:016x}"
                mismatches.append(mismatch)

        return {
            'csr_mismatches': csr_mismatches,
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
