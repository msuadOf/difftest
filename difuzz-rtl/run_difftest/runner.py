import os
import sys

import struct

from cocotb.decorators import coroutine
from RTLSim.host import ILL_MEM, SUCCESS, TIME_OUT, ASSERTION_FAIL
from src.utils import setup, run_isa_test
from src.multicore_manager import proc_state

def parse_elf_symbols(elf_file, out_dir):
    symbols = {}
    try:
        from elftools.elf.elffile import ELFFile
        from elftools.elf.sections import SymbolTableSection
    except ImportError as exc:
        raise ImportError(
            'parse_elf_symbols 需要 pyelftools；请在容器内先执行 difuzz-rtl/setup.sh '
            '或安装 `pip3 install pyelftools`。'
        ) from exc

    with open(elf_file, 'rb') as fd:
        elf = ELFFile(fd)
        load_segments = [
            seg for seg in elf.iter_segments()
            if seg['p_type'] == 'PT_LOAD'
        ]

        for section in elf.iter_sections():
            if not isinstance(section, SymbolTableSection):
                continue

            for sym in section.iter_symbols():
                symbol = sym.name
                addr = sym['st_value']
                if symbol:
                    symbols[symbol] = addr

        sym_name = os.path.join(out_dir, 'elf_payload.symbols')
        with open(sym_name, 'w') as sym_fd:
            for symbol, addr in sorted(symbols.items(), key=lambda item: item[1]):
                sym_fd.write(f'{addr:016x} {symbol}\n')

        if '_start' not in symbols:
            raise KeyError("The provided ELF file MUST contain a '_start' symbol.")
        if '_end_main' not in symbols:
            raise KeyError("The provided ELF file MUST contain a '_end_main' symbol.")
        if 'tohost' not in symbols:
            raise KeyError("The provided ELF file MUST contain a 'tohost' symbol.")
        if 'begin_signature' not in symbols:
            raise KeyError("The provided ELF file MUST contain a 'begin_signature' symbol.")
        if 'end_signature' not in symbols:
            raise KeyError("The provided ELF file MUST contain a 'end_signature' symbol.")

        for n in range(6):
            if f'_random_data{n}' not in symbols:
                raise KeyError(f"The provided ELF file MUST contain a '_random_data{n}' symbol.")
            if f'_end_data{n}' not in symbols:
                raise KeyError(f"The provided ELF file MUST contain a '_end_data{n}' symbol.")

        def read_elf_range(addr, size):
            chunks = bytearray()
            cursor = addr
            end_addr = addr + size

            while cursor < end_addr:
                segment = next(
                    (
                        seg for seg in load_segments
                        if seg['p_vaddr'] <= cursor < seg['p_vaddr'] + seg['p_memsz']
                    ),
                    None
                )

                if segment is None:
                    chunks.append(0)
                    cursor += 1
                    continue

                seg_start = segment['p_vaddr']
                seg_file_end = seg_start + segment['p_filesz']
                seg_mem_end = seg_start + segment['p_memsz']
                read_end = min(end_addr, seg_mem_end)

                if cursor < seg_file_end:
                    file_end = min(read_end, seg_file_end)
                    seg_offset = cursor - seg_start
                    file_size = file_end - cursor
                    chunks.extend(segment.data()[seg_offset:seg_offset + file_size])
                    cursor = file_end
                else:
                    zero_size = read_end - cursor
                    chunks.extend(b'\x00' * zero_size)
                    cursor = read_end

            return bytes(chunks)

        random_data = []
        for n in range(6):
            start_d = symbols[f'_random_data{n}']
            end_d = symbols[f'_end_data{n}']
            if end_d > start_d:
                size = end_d - start_d
                data_bytes = read_elf_range(start_d, size)
                for i in range(0, size, 8):
                    word_bytes = data_bytes[i:i + 8]
                    word = struct.unpack('<Q', word_bytes.ljust(8, b'\x00'))[0]
                    random_data.append(word)

    return symbols, random_data


def prepare_elf_input(elf_file, out_dir, max_cycles=100000):
    """将单个 ELF 文件转换为 RTL 和 ISA 仿真输入（rtlInput + isaInput）"""
    import subprocess

    symbols, random_data = parse_elf_symbols(elf_file, out_dir)

    hex_file = os.path.join(out_dir, 'elf_payload.hex')
    subprocess.call([
        'riscv64-unknown-elf-elf2hex',
        '--bit-width', '64',
        '--input', elf_file,
        '--output', hex_file,
    ])

    # 补零防越界（host.py 会多读 36 字节）
    with open(hex_file, 'a') as f:
        for _ in range(16):
            f.write('0000000000000000\n')

    intr_file = os.path.join(out_dir, 'dummy.intr')
    open(intr_file, 'w').close()

    from RTLSim.host import rtlInput
    from ISASim.host import isaInput

    rtl_input = rtlInput(hex_file, intr_file, random_data, symbols, max_cycles)
    isa_input = isaInput(elf_file, intr_file)

    return rtl_input, isa_input, symbols


@coroutine
def RunDifftest(dut, toplevel, template='../Fuzzer/Template',
                elf_file='', elf_dir='', out='output', max_cycles=100000, debug=False):
    """
    Difftest 主协程，支持批量 ELF 执行。

    核心思路（与 Fuzzer.py 一致）：
      setup() 只调用一次 → 循环中每次调用 rtlHost.run_test()，
      run_test 内部会完成 memory 重建、hex 加载、硬件 reset、adapter start/stop，
      无需重启整个 Verilator 仿真环境。
    """

    # setup 只做一次，仿真环境（rtlHost/isaHost/checker）在整个批次中复用
    (mutator, preprocessor, isaHost, rtlHost, checker) = setup(
        dut, toplevel, template, out, 0, debug, minimizing=False, no_guide=True
    )

    def debug_p(msg, highlight=False):
        if highlight or debug:
            if highlight:
                print('\x1b[1;31m' + msg + '\x1b[0m')
            else:
                print(msg)

    # ── 收集待测试 ELF 文件 ──
    elf_files = []
    if elf_dir:
        # 用 os.walk 递归查找，避免 glob ** 在某些环境/版本下不可靠
        for root, _dirs, files in os.walk(elf_dir):
            for f in files:
                if f.endswith('.elf'):
                    elf_files.append(os.path.join(root, f))
        elf_files.sort()
        if not elf_files:
            debug_p(f'[Difftest] ELF 目录 "{elf_dir}" 中未找到 .elf 文件', True)
            return
        debug_p(f'[Difftest] 批量模式：在 "{elf_dir}" 中找到 {len(elf_files)} 个 ELF 文件', True)
    elif elf_file:
        elf_files = [elf_file]
    else:
        raise ValueError('ELF_FILE 或 ELF_DIR 必须指定其中一个！')

    total = len(elf_files)
    passed = 0
    failed = 0
    results = []

    print(f'\x1b[1;32m[Difftest] 开始批量执行 ({total} 个测试)\x1b[0m')

    for idx, current_elf in enumerate(elf_files):
        elf_name = os.path.basename(current_elf)
        debug_p(
            f'\x1b[1;36m[Difftest] [{idx + 1}/{total}] 加载: {elf_name}\x1b[0m',
            True,
        )

        # 每个 ELF 使用独立子目录，避免 hex/symbols 等中间文件冲突
        test_out = os.path.join(out, f'test_{idx:04d}')
        os.makedirs(test_out, exist_ok=True)

        # ── 1. 解析 ELF 并生成仿真输入 ──
        try:
            rtl_input, isa_input, symbols = prepare_elf_input(
                current_elf, test_out, max_cycles,
            )
        except Exception as e:
            debug_p(f'[Difftest] [{idx + 1}/{total}] 解析错误: {e}', True)
            failed += 1
            results.append((elf_name, 'Parse Error', str(e)))
            continue

        assert_intr = False
        stop = [proc_state.NORMAL]

        # ── 2. 运行 ISA 仿真（Spike） ──
        ret = run_isa_test(isaHost, isa_input, stop, test_out, 0, assert_intr, timeout=2)
        if ret == proc_state.ERR_ISA_TIMEOUT:
            debug_p(f'[Difftest] [{idx + 1}/{total}] ISA 超时', True)
            failed += 1
            results.append((elf_name, 'ISA Timeout', '-'))
            continue
        elif ret == proc_state.ERR_ISA_ASSERT:
            debug_p(f'[Difftest] [{idx + 1}/{total}] ISA 断言失败', True)
            failed += 1
            results.append((elf_name, 'ISA Assert Fail', '-'))
            continue

        # ── 3. 运行 RTL 仿真（内部 reset 状态，无需重启仿真环境） ──
        try:
            (ret, coverage) = yield rtlHost.run_test(rtl_input, assert_intr)
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            debug_p(
                f'[Difftest] [{idx + 1}/{total}] RTL 仿真错误: {e}\n{traceback_str}',
                True,
            )
            failed += 1
            results.append((elf_name, 'RTL Error', str(e)))
            continue

        # ── 4. 对比结果 ──
        cause = '-'
        match = False
        if ret == SUCCESS:
            match = checker.check(symbols)
        elif ret == ILL_MEM:
            match = True
            debug_p(f'[Difftest] [{idx + 1}/{total}] 内存访问越界 DRAM 区域', True)

        if not match or ret not in [SUCCESS, ILL_MEM]:
            if ret == TIME_OUT:          cause = 'Timeout'
            elif ret == ASSERTION_FAIL:  cause = 'Assertion Fail'
            else:                        cause = 'Mismatch'
            debug_p(
                f'\x1b[1;31m[Difftest] [{idx + 1}/{total}] FAIL [{cause}] - {elf_name}\x1b[0m',
                True,
            )
            failed += 1
            results.append((elf_name, 'FAIL', cause))
        else:
            print(f'\x1b[1;32m[Difftest] [{idx + 1}/{total}] PASS - {elf_name}\x1b[0m')
            passed += 1
            results.append((elf_name, 'PASS', '-'))

    # ── 汇总报告 ──
    print(f'\n\x1b[1;32m{"=" * 60}\x1b[0m')
    print(f'\x1b[1;32m[Difftest] 批量测试汇总: {passed}/{total} 通过, {failed}/{total} 失败\x1b[0m')
    print(f'\x1b[1;32m{"=" * 60}\x1b[0m')
    for name, status, detail in results:
        color = '\x1b[1;32m' if status == 'PASS' else '\x1b[1;31m'
        line = f'  {color}{status:15s}\x1b[0m {name}'
        if detail != '-':
            line += f' ({detail})'
        print(line)

    # 写结果到文件
    result_file = os.path.join(out, 'results.txt')
    with open(result_file, 'w') as f:
        for name, status, detail in results:
            f.write(f'{status}\t{name}\t{detail}\n')
    debug_p(f'[Difftest] 结果已写入 {result_file}')
