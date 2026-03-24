import os

from riscv_definitions import *

class sigChecker():
    def __init__(self, isa_sigfile, rtl_sigfile, debug=False, minimizing=False, isa_width=None, wrapped_elf=False):
        self.isa_sigfile = isa_sigfile
        self.rtl_sigfile = rtl_sigfile

        self.debug = debug
        self.minimizing = minimizing
        self.isa_width = isa_width  # 'rv32' or 'rv64' - explicit ISA width from ELF metadata
        self.wrapped_elf = wrapped_elf  # True if this is a wrapped ELF (not a pre-instrumented direct ELF)

        # CSR/PMP comparison policy:
        # - Skip CSRs that have known ISA vs RTL differences (PMP)
        # - Normalize CSRs by masking out non-essential bits
        # Note: Exception CSRs (mcause, mepc, mtval) are now checked to detect
        #       differences in exception handling behavior
        self.skip_csrs = {
            # PMP configuration - different defaults between Spike and RTL
            'pmpcfg0', 'pmpaddr0', 'pmpaddr1', 'pmpaddr2', 'pmpaddr3', 'pmpaddr4',
        }

        self.normalize_csrs = {
            # Mask out SD (dirty) bit in sstatus/mstatus
            # In RV32, SD is at bit 31 (0x80000000)
            # In RV64, SD is at bit 63 (0x8000000000000000)
            # We dynamically detect ISA width and apply appropriate mask
            'sstatus': 'dynamic_sd_mask',
            'mstatus': 'dynamic_sd_mask',
        }

    def _normalize_csr_value(self, csr_name, isa_val, rtl_val):
        """
        Normalize CSR values by clearing the SD (dirty) bit.

        For RV32: SD is at bit 31 (mask: 0x7FFFFFFF)
        For RV64: SD is at bit 63 (mask: 0x7FFFFFFFFFFFFFFF)

        Uses explicit ISA width from ELF metadata if available, otherwise falls back
        to value-based detection for backward compatibility.

        Returns (normalized_isa_val, normalized_rtl_val)
        """
        # Use explicit ISA width if provided
        if self.isa_width == 'rv64':
            is_rv64 = True
        elif self.isa_width == 'rv32':
            is_rv64 = False
        else:
            # Fallback to value-based detection for backward compatibility
            # This path is taken when isa_width is not explicitly provided
            # Note: This fallback can produce false matches for RV64 values (see test_rv64_bit31_preservation_key)
            max_val = max(isa_val, rtl_val)
            is_rv64 = max_val > 0xFFFFFFFF or (max_val >> 63) & 1

        if is_rv64:
            # RV64: clear bit 63 (SD bit position)
            mask = 0x7FFFFFFFFFFFFFFF
        else:
            # RV32: clear bit 31 (SD bit position)
            mask = 0x7FFFFFFF

        return (isa_val & mask, rtl_val & mask)

    def debug_print(self, message, highlight=False):
        if highlight and not self.minimizing:
            print('\x1b[1;31m' + message + '\x1b[1;m')
        elif self.debug:
            print(message)

    def read_symbols(self, symbols):
        symbol_start = symbols['begin_signature']
        symbol_end = symbols['end_signature']
        xreg_idxes = [ (symbols['reg_x{}_output'.format(i)] - symbol_start) // 8 \
                       for i in range(32) ]
        freg_idxes = [ (symbols['reg_f{}_output'.format(i)] - symbol_start) // 8 \
                       for i in range(32) ]
        csr_idxes = {}
        for csr_name in csr_names:
            csr_idxes[csr_name] = (symbols[csr_name + '_output'] - symbol_start) // 8

        data_symbols = []
        for i in range(6):
            data_start = symbols['_random_data{}'.format(i)]
            data_end = symbols['_end_data{}'.format(i)]

            data_symbols.append((data_start, data_end))

        data_idx_start = (symbol_end - symbol_start) // (2 * 8)

        return (xreg_idxes, freg_idxes, csr_idxes, data_symbols, data_idx_start)

    def read_sig(self, sigfile, xreg_idxes, freg_idxes,
                 csr_idxes, data_symbols, data_idx_start):

        fd = open(sigfile)
        lines = fd.readlines()
        fd.close()

        xreg_vals = []
        freg_vals = []
        csr_vals = {}

        for idx in xreg_idxes:
            val = lines[idx // 2][16 - 16 * (idx % 2):32 - 16 * (idx % 2)]
            xreg_vals.append(int(val, 16))

        for idx in freg_idxes:
            val = lines[idx // 2][16 - 16 * (idx % 2):32 - 16 * (idx % 2)]
            freg_vals.append(int(val, 16))

        for csr_name in csr_names:
            idx = csr_idxes[csr_name]
            val = lines[idx // 2][16 - 16 * (idx % 2):32 - 16 * (idx % 2)]
            csr_vals[csr_name] = int(val, 16)

        data_vals = {}
        for i in range(6):
            tup = data_symbols[i]
            data_start = tup[0]
            data_end = tup[1]
            section_size = data_end - data_start

            data = []
            for j in range(section_size // 16):
                words = lines[data_idx_start + j]
                data.append(int(words[16:32], 16))
                data.append(int(words[0:16], 16))

            data_vals['data{}'.format(i)] = data
            data_idx_start += (section_size // 16)

        return (xreg_vals, freg_vals, csr_vals, data_vals)

    def check_intr(self, symbols):
        (xreg_idxes, freg_idxes, csr_idxes, data_symbols, data_idx_start) = \
            self.read_symbols(symbols)

        (rtl_xreg_vals, rtl_freg_vals, rtl_csr_vals, rtl_data_vals) = \
            self.read_sig(self.rtl_sigfile, xreg_idxes, freg_idxes,
                          csr_idxes, data_symbols, data_idx_start)

        scause = rtl_csr_vals['scause']
        sepc = rtl_csr_vals['sepc']
        mcause = rtl_csr_vals['mcause']
        mepc = rtl_csr_vals['mepc']

        intr_prv = NONE
        epc = 0
        # TODO, implements multiple interrupt assertion and priviledges
        assert (scause >> 63) & (mcause >> 63) & 1 == 0, \
            "Only one of Supervisor or Machine interrupt can be asserted"

        if (scause >> 63) & 1:
            intr_prv = SUPERVISOR
            epc = sepc
        elif (mcause >> 63) & 1:
            intr_prv = MACHINE
            epc = mepc

        self.debug_print('[DifuzzRTL] {} interrupt handled -- epc {:016x}'.
                         format(prv[intr_prv], epc), intr_prv != NONE)

        return intr_prv, epc

    def check(self, symbols):

        (xreg_idxes, freg_idxes, csr_idxes, data_symbols, data_idx_start) = \
            self.read_symbols(symbols)

        (isa_xreg_vals, isa_freg_vals, isa_csr_vals, isa_data_vals) = \
            self.read_sig(self.isa_sigfile, xreg_idxes, freg_idxes,
                          csr_idxes, data_symbols, data_idx_start)

        (rtl_xreg_vals, rtl_freg_vals, rtl_csr_vals, rtl_data_vals) = \
            self.read_sig(self.rtl_sigfile, xreg_idxes, freg_idxes,
                          csr_idxes, data_symbols, data_idx_start)

        xreg_match = True
        freg_match = True
        csr_match = True
        data_match = True

        # Get mcause values to determine exception type
        isa_mcause = isa_csr_vals.get('mcause', 0)
        rtl_mcause = rtl_csr_vals.get('mcause', 0)

        # Exception code is in low 7 bits (bit 63 or 7 is interrupt flag depending on XLEN)
        # We need to compare both exception code AND interrupt flag
        isa_exc_code = isa_mcause & 0x7F  # Low 7 bits: exception cause
        rtl_exc_code = rtl_mcause & 0x7F
        isa_interrupt = (isa_mcause >> 63) & 1  # Interrupt flag (bit 63 in RV64, bit 7 in RV32)
        rtl_interrupt = (rtl_mcause >> 63) & 1
        # Same exception type means both exception code AND interrupt flag match
        same_exception_type = (isa_exc_code == rtl_exc_code) and (isa_interrupt == rtl_interrupt)

        for (i, val) in enumerate(zip(isa_xreg_vals, rtl_xreg_vals)):
            match = (val[0] == val[1])
            if not match: xreg_match = False
            self.debug_print('(x{:02} |{:>5}) [ISA] {:016x} || [RTL] {:016x}'. \
                             format(i, xreg_names[i], val[0], val[1]), not match)

        for (i, val) in enumerate(zip(isa_freg_vals, rtl_freg_vals)):
            match = (val[0] == val[1])
            if not match: freg_match = False
            self.debug_print('(f{:02} |{:>5}) [ISA] {:016x} || [RTL] {:016x}'. \
                             format(i, freg_names[i], val[0], val[1]), not match)

        for csr_name in csr_names:
            isa_val = isa_csr_vals[csr_name]
            rtl_val = rtl_csr_vals[csr_name]

            # Apply comparison policy
            if csr_name in self.skip_csrs:
                # Skip this CSR - don't report mismatches
                continue

            if csr_name in self.normalize_csrs:
                policy = self.normalize_csrs[csr_name]
                if policy == 'dynamic_sd_mask':
                    # Dynamically detect ISA width and apply appropriate SD mask
                    isa_val, rtl_val = self._normalize_csr_value(csr_name, isa_val, rtl_val)
                    match = (isa_val == rtl_val)
                    if not match: csr_match = False
                    # Debug without showing original vs normalized to reduce clutter
                    self.debug_print('({:>10}) [ISA] {:016x} || [RTL] {:016x}'. \
                                     format(csr_name, isa_val, rtl_val), not match)
                else:
                    # Fixed mask policy (not currently used)
                    mask = policy
                    isa_val_normalized = isa_val & mask
                    rtl_val_normalized = rtl_val & mask
                    match = (isa_val_normalized == rtl_val_normalized)
                    if not match: csr_match = False
                    self.debug_print('({:>10}) [ISA] {:016x} (norm: {:016x}) || [RTL] {:016x} (norm: {:016x})'. \
                                     format(csr_name, isa_val, isa_val_normalized, rtl_val, rtl_val_normalized), not match)
            else:
                match = (isa_val == rtl_val)

                # Special handling for trap CSRs (mcause, mepc, mtval):
                #
                # For wrapped ELFs: skip trap CSRs only for ecall exits (wrapper mechanism).
                # For payload exceptions (illegal instruction, access fault, etc.), compare
                # trap CSRs to detect real ISA/RTL disagreements.
                #
                # For direct (pre-instrumented) ELFs: use fine-grained comparison:
                # - If exception types differ, report mcause mismatch
                # - If exception types match:
                #   - For ecall exits (mcause=8 or 11), skip mepc/mtval (timing-dependent)
                #   - For other exceptions, compare mepc/mtval (distinguishes trap location)
                if self.wrapped_elf and csr_name in ['mcause', 'mepc', 'mtval']:
                    # Wrapped ELF - check if this is an ecall exit (normal termination)
                    # ECALL has cause code 8 (user) or 11 (machine) WITHOUT interrupt flag set
                    # Machine external interrupts also use code 11 but have interrupt flag set
                    is_ecall_exit = (
                        isa_exc_code in [8, 11] and
                        rtl_exc_code in [8, 11] and
                        not isa_interrupt and
                        not rtl_interrupt
                    )
                    if is_ecall_exit:
                        # Ecall exit via wrapper - skip trap CSR comparison
                        # These CSRs reflect the wrapper's ecall mechanism, not payload behavior
                        continue
                    else:
                        # Payload exception or interrupt - compare trap CSRs normally
                        # This catches real bugs where Spike and RTL raise different exceptions
                        if not match: csr_match = False
                        self.debug_print('({:>10}) [ISA] {:016x} || [RTL] {:016x}'. \
                                         format(csr_name, isa_val, rtl_val), not match)
                elif csr_name == 'mcause' and not same_exception_type:
                    # Direct ELF, different exception types - report mcause mismatch
                    if not match: csr_match = False
                    self.debug_print('({:>10}) [ISA] {:016x} || [RTL] {:016x}'. \
                                     format(csr_name, isa_val, rtl_val), not match)
                elif csr_name in ['mepc', 'mtval'] and same_exception_type:
                    # Direct ELF, same exception type - check if ecall exit
                    is_ecall_exit = (isa_exc_code in [8, 11])
                    if is_ecall_exit:
                        # Ecall exit - skip mepc/mtval comparison (timing-dependent)
                        continue
                    else:
                        # Other exception - compare mepc/mtval (distinguishes trap location)
                        if not match: csr_match = False
                        self.debug_print('({:>10}) [ISA] {:016x} || [RTL] {:016x}'. \
                                         format(csr_name, isa_val, rtl_val), not match)
                else:
                    # Normal comparison for other CSRs, or mcause when exception types match
                    if not match: csr_match = False
                    self.debug_print('({:>10}) [ISA] {:016x} || [RTL] {:016x}'. \
                                     format(csr_name, isa_val, rtl_val), not match)

        for i in range(6): # TODO, max_sections = 6
            data_start = data_symbols[i][0]
            isa_data = isa_data_vals['data{}'.format(i)]
            rtl_data = rtl_data_vals['data{}'.format(i)]

            if isa_data != rtl_data:
                data_match = False
                self.debug_print('(_random_data{})'.format(i), not data_match)
                for (j, words) in enumerate(zip(isa_data, rtl_data)):
                    addr = data_start + 8 * j
                    isa_word = words[0]
                    rtl_word = words[1]

                    match = (isa_word == rtl_word)
                    self.debug_print('({:016x}) [ISA] {:016x} || [RTL] {:016x}'. \
                                     format(addr, isa_word, rtl_word), not match)

        return (xreg_match & freg_match & csr_match & data_match)
