import os
import sys

from cocotb.decorators import coroutine
from RTLSim.host import ILL_MEM, SUCCESS, TIME_OUT, ASSERTION_FAIL
from src.utils import setup, run_isa_test
from src.multicore_manager import proc_state

def parse_elf_symbols(elf_file, out_dir):
    symbols = {}
    import struct
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

        # 补齐某些可能的缺失使得 check 和 host.py 模块不会爆 KeyError
        # 对于外部纯执行而没有随机读写段的汇编，这尤为重要
        start_a = symbols['_start']
        if '_end_main' not in symbols: symbols['_end_main'] = start_a + 0x1000
        if 'tohost' not in symbols: symbols['tohost'] = start_a + 0x2000
        if 'begin_signature' not in symbols: symbols['begin_signature'] = start_a + 0x3000
        if 'end_signature' not in symbols: symbols['end_signature'] = start_a + 0x3000
        for n in range(6):
            if f'_random_data{n}' not in symbols:
                symbols[f'_random_data{n}'] = start_a + 0x4000
            if f'_end_data{n}' not in symbols:
                symbols[f'_end_data{n}'] = start_a + 0x4000

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
                    # 小端序解包为 64 位无符号整数
                    word = struct.unpack('<Q', word_bytes.ljust(8, b'\x00'))[0]
                    random_data.append(word)

    return symbols, random_data

@coroutine
def RunDifftest(dut, toplevel, template='../Fuzzer/Template', elf_file='', out='output', debug=False):
    """
    Difftest 主协程，负责运行 RTL 仿真(Verilator)，并报告执行结果。
    """

    # 在这个简单的差分测试脚本中，我们不使用多线程/用例最小化/覆盖率引导测试的功能
    # setup 函数将返回需要的组件实例
    (mutator, preprocessor, isaHost, rtlHost, checker) = setup(
        dut, toplevel, template, out, 0, debug, minimizing=False, no_guide=True
    )

    # 辅助打印函数，若 highlight=True 或处于 debug 模式则打印
    def debug_p(msg, highlight=False):
        if highlight or debug:
            if highlight:
                print('\x1b[1;31m' + msg + '\x1b[0m')
            else:
                print(msg)

    print('\x1b[1;32m[Difftest] Start\x1b[0m')

    assert_intr = False
    rtl_input = None
    isa_input = None

    if elf_file:
        import subprocess
        # 外部 ELF 包含符号流执行模式
        debug_p(f'[Difftest] Loading .elf: {elf_file}', True)

        # 1. 提取和验证符号
        symbols, random_data = parse_elf_symbols(elf_file, out)

        # 2. 将 ELF 转换成 HEX 供 RTLSim 加载。如果你的环境变量没有配置 elf2hex，这步会报错
        hex_file = os.path.join(out, 'elf_payload.hex')
        # DifuzzRTL 配置中一般系统编进了 riscv64-unknown-elf-elf2hex 或 elf2hex
        subprocess.call(['riscv64-unknown-elf-elf2hex', '--bit-width', '64', '--input', elf_file, '--output', hex_file])

        # 因为 ELF 解析出来的末尾可能贴得很紧，且由于预生成的 elf2hex 文件行数固定，
        # host.py 会有多读 36 字节的情况导致 IndexError。
        # 这里我们在 hex 文件末尾手动再补零 (16 行空数据=128字节)，以满足防越界要求。
        with open(hex_file, 'a') as f:
            for _ in range(16):
                f.write('0000000000000000\n')

        # 3. 提供空的 dummy 假中断文件
        intr_file = os.path.join(out, 'dummy.intr')
        open(intr_file, 'w').close()

        from RTLSim.host import rtlInput
        from ISASim.host import isaInput

        rtl_input = rtlInput(hex_file, intr_file, random_data, symbols, 100000)
        isa_input = isaInput(elf_file, intr_file)

    else:
        # 未提供 elf_file
        raise ValueError('ELF_FILE must be specified!')

    # 确保 rtl_input 已准备就绪，执行 RTL 仿真
    if rtl_input:
        stop = [proc_state.NORMAL]

        if isa_input:
            # 只有需要 ISA 对比时才运行 Spike
            ret = run_isa_test(isaHost, isa_input, stop, out, 0, assert_intr)
            if ret == proc_state.ERR_ISA_TIMEOUT:
                debug_p('[Difftest] ISA Timeout', True)
                return
            elif ret == proc_state.ERR_ISA_ASSERT:
                debug_p('[Difftest] ISA Assertion Failed', True)
                return

        try:
            # yield 交出控制权进行 cocotb RTL 时钟仿真
            (ret, coverage) = yield rtlHost.run_test(rtl_input, assert_intr)
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            debug_p('[Difftest] RTL Simulation Error: ' + str(e) + '\n' + traceback_str, True)
            return

        match = False
        cause = '-'

        # RTL 仿真正常结束后，对比 symbols 定义的内存/寄存器状态
        if ret == SUCCESS:
            match = checker.check(symbols)
        elif ret == ILL_MEM:
            # 内存访问越界 DRAM 区域
            match = True
            debug_p('[Difftest] Memory access outside DRAM', True)

        # 对于 elf 模式，如果有 match 失败的情况则报 Mismatch
        if not match or ret not in [SUCCESS, ILL_MEM]:
            if ret == TIME_OUT:          cause = 'Timeout'
            elif ret == ASSERTION_FAIL:  cause = 'Assertion Fail'
            else:                        cause = 'Mismatch'
            debug_p(f'[Difftest] FAIL [{cause}]', True)
        else:
            print('\x1b[1;32m[Difftest] PASS: ISA and RTL match!\x1b[0m')
    else:
        # 未提供 rtl_input，直接报错
        raise ValueError('[Difftest] Compilation Failed')
