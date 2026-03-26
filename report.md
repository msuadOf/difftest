# Difuzz-RTL 执行流程分析报告

## 1. 执行流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              程序启动                                        │
│              difuzz-rtl/Fuzzer/DifuzzRTL.py (入口文件)                        │
│              通过 TestFactory(Run) 调用 Fuzzer.py:12 (Run 协程)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: 组件初始化 setup()                                                 │
│  ├─ 调用位置: Fuzzer.py:23                                                  │
│  ├─ 定义位置: utils.py:92                                                   │
│  └─ 调用链:                                                                  │
│      ├─ utils.py:93  → mutator.py:93      (rvMutator)                       │
│      ├─ utils.py:97  → preprocessor.py:10 (rvPreProcessor)                  │
│      ├─ utils.py:106 → ISASim/host.py:10  (rvISAhost)                       │
│      ├─ utils.py:107 → RTLSim/host.py:24  (rvRTLhost)                       │
│      └─ utils.py:109 → signature_checker.py:5 (sigChecker)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 2: 主循环 Run() 开始                                                  │
│  ├─ 定义位置: Fuzzer.py:12                                                  │
│  ├─ 循环开始: Fuzzer.py:39                                                  │
│  └─ 循环条件: while it < num_iter:                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐              ┌───────────────────┐
        │ Step 3: 生成输入  │              │ Step 4: 预处理    │
        │                   │              │                   │
        │ 调用位置:         │───►          │ 调用位置:         │
        │ Fuzzer.py:53      │              │ Fuzzer.py:60      │
        │                   │              │                   │
        │ mutator.get()     │              │ preprocessor.     │
        │ 定义位置:          │              │ process()         │
        │ mutator.py:356    │              │ 定义位置:          │
        │                   │              │ preprocessor.py:57│
        └───────────────────┘              └─────────┬─────────┘
                                                      │
                    ┌─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 5: ISA 模拟执行                                                       │
│  ├─ 调用位置: Fuzzer.py:63                                                  │
│  ├─ 调用函数: run_isa_test()                                                │
│  ├─ 定义位置: utils.py:52                                                   │
│  └─ 内部调用: utils.py:57 → ISASim/host.py:22 (isaHost.run_test)            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 6: RTL 模拟执行                                                       │
│  ├─ 调用位置: Fuzzer.py:68                                                  │
│  ├─ 调用方法: rtlHost.run_test()                                            │
│  ├─ 定义位置: RTLSim/host.py:111                                            │
│  └─ 内部调用链:                                                              │
│      ├─ RTLSim/host.py:125 → RTLSim/host.py:46 (set_bootrom)                │
│      ├─ RTLSim/host.py:164 → RTLSim/host.py:81 (reset)                      │
│      ├─ RTLSim/host.py:166 → tile_adapter.py:111 (adapter.start)            │
│      ├─ RTLSim/host.py:175 → tile_adapter.py:105 (probe_tohost)             │
│      ├─ RTLSim/host.py:177 → tile_adapter.py:120 (adapter.stop)             │
│      └─ RTLSim/host.py:197 → RTLSim/host.py:93 (save_signature)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 7: 结果比较 checker.check()                                           │
│  ├─ 调用位置: Fuzzer.py:85                                                  │
│  ├─ 定义位置: signature_checker.py:114                                      │
│  └─ 内部调用:                                                                │
│      ├─ signature_checker.py:116 → :19 (read_symbols)                       │
│      ├─ signature_checker.py:119 → :41 (read_sig ISA)                       │
│      └─ signature_checker.py:123 → :41 (read_sig RTL)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐              ┌───────────────────┐
        │    Match          │              │    Mismatch       │
        │    继续循环       │              │    保存用例       │
        │                   │              │                   │
        │ Fuzzer.py:84-85   │              │ Fuzzer.py:95-110  │
        │ if ret == SUCCESS │              │ if not match:     │
        └───────────────────┘              └───────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 8: 覆盖率引导 (若覆盖率增长)                                          │
│  ├─ 调用位置: Fuzzer.py:112 (if coverage > last_coverage)                   │
│  └─ 调用链:                                                                  │
│      ├─ Fuzzer.py:118 → utils.py:76 (save_file)                             │
│      ├─ Fuzzer.py:121 → mutator.py:38 (sim_input.save)                      │
│      ├─ Fuzzer.py:124 → mutator.py:450 (mutator.add_corpus)                │
│      └─ Fuzzer.py:127 → mutator.py:438 (mutator.update_phase)              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │  下一轮循环   │
                              │  it += 1      │
                              │  Fuzzer.py:39 │
                              └───────────────┘
```

---

## 2. 详细执行流程（按顺序）

### Step 1: 程序入口 - 参数解析

**文件**: `difuzz-rtl/Fuzzer/DifuzzRTL.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| `DifuzzRTL.py:41` | `parser = envParser()` | 创建环境变量解析器 |
| `DifuzzRTL.py:43` | `parser.add_option('toplevel', ...)` | 添加 toplevel 参数 |
| `DifuzzRTL.py:44` | `parser.add_option('num_iter', ...)` | 添加迭代次数参数 |
| `DifuzzRTL.py:46` | `parser.add_option('template', ...)` | 添加模板参数 |

**创建输出目录**:

| 行号 | 代码 | 说明 |
|------|------|------|
| `DifuzzRTL.py:74` | `os.makedirs(out + '/mismatch')` | 创建 mismatch 目录 |
| `DifuzzRTL.py:86` | `os.makedirs(out + '/corpus')` | 创建 corpus 目录 |
| `DifuzzRTL.py:89` | `datetime.today().strftime(...)` | 获取当前日期 |
| `DifuzzRTL.py:90` | `cov_log = out + '/cov_log_{}.txt'` | 设置覆盖率日志文件名 |

---

### Step 2: 选择执行模式

**文件**: `difuzz-rtl/Fuzzer/DifuzzRTL.py`

#### 单核模式

| 行号 | 代码 | 说明 |
|------|------|------|
| `DifuzzRTL.py:97` | `if not multicore:` | 判断是否单核模式 |
| `DifuzzRTL.py:98` | `if minimize:` | 判断是否最小化模式 |
| `DifuzzRTL.py:106` | `factory = TestFactory(Run)` | 创建 Run 测试工厂 |
| `DifuzzRTL.py:111` | `factory.generate_tests()` | 生成测试 |

> **跨文件调用说明**:
> - **调用位置**: `DifuzzRTL.py:106`
> - **调用的函数**: `Run` 协程
> - **函数定义位置**: `Fuzzer.py:12`
> [difuzz-rtl/Fuzzer/src/multicore_manager.py#L196-L206](difuzz-rtl/Fuzzer/src/multicore_manager.py#L196-L206)

#### 多核模式

| 行号 | 代码 | 说明 |
|------|------|------|
| `DifuzzRTL.py:113` | `else:` | 多核模式分支 |
| `DifuzzRTL.py:114` | `manager = procManager(multicore, out, date)` | 创建进程管理器 |

> **跨文件调用说明**:
> - **调用位置**: `DifuzzRTL.py:114`
> - **调用的类**: `procManager`
> - **类定义位置**: `multicore_manager.py:38`

---

### Step 3: 组件初始化 setup()

**调用位置**: `Fuzzer.py:23`
```python
(mutator, preprocessor, isaHost, rtlHost, checker) = \
    setup(dut, toplevel, template, out, proc_num, debug, no_guide=no_guide)
```

**函数定义位置**: `utils.py:92`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:93` | `mutator = rvMutator(no_guide=no_guide)` | 创建指令变异器 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:93`
> - **调用的类**: `rvMutator`
> - **类定义位置**: `mutator.py:93`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:97` | `preprocessor = rvPreProcessor(cc, elf2hex, template, out, proc_num)` | 创建预处理器 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:97`
> - **调用的类**: `rvPreProcessor`
> - **类定义位置**: `preprocessor.py:10`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:106` | `isaHost = rvISAhost(spike, spike_arg, isa_sigfile)` | 创建 ISA 模拟器 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:106`
> - **调用的类**: `rvISAhost`
> - **类定义位置**: `ISASim/host.py:10`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:107` | `rtlHost = rvRTLhost(dut, toplevel, rtl_sigfile, debug=debug)` | 创建 RTL 模拟器 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:107`
> - **调用的类**: `rvRTLhost`
> - **类定义位置**: `RTLSim/host.py:24`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:109` | `checker = sigChecker(isa_sigfile, rtl_sigfile, debug, minimizing)` | 创建签名检查器 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:109`
> - **调用的类**: `sigChecker`
> - **类定义位置**: `signature_checker.py:5`

---

### Step 4: 生成测试输入 mutator.get()

**调用位置**: `Fuzzer.py:53`
```python
(sim_input, data) = mutator.get(assert_intr)
```

**函数定义位置**: `mutator.py:356`

#### 4.1 确定变异阶段

| 行号 | 代码 | 说明 |
|------|------|------|
| `mutator.py:366` | `if self.phase == GENERATION:` | 判断是否为生成阶段 |
| `mutator.py:377` | `elif self.phase in [ MUTATION, MERGE ]:` | 判断是否为变异或合并阶段 |

#### 4.2 GENERATION 阶段 - 生成指令

| 行号 | 代码 | 说明 |
|------|------|------|
| `mutator.py:367` | `for n in range(self.num_prefix):` | 循环生成前缀指令 |
| `mutator.py:368` | `word = self.inst_generator.get_word(PREFIX)` | 获取一个前缀指令字 |

> **跨文件调用说明**:
> - **调用位置**: `mutator.py:368`
> - **调用点所属对象**: `self.inst_generator` (类型: `rvInstGenerator`)
> - **调用的方法**: `get_word()`
> - **方法定义位置**: `inst_generator.py:158`

| 行号 | 代码 | 说明 |
|------|------|------|
| `mutator.py:370` | `for n in range(self.num_words):` | 循环生成主指令 |
| `mutator.py:371` | `word = self.inst_generator.get_word(MAIN)` | 获取一个主指令字 |

> **跨文件调用说明**:
> - **调用位置**: `mutator.py:371`
> - **调用的方法**: `get_word()`
> - **方法定义位置**: `inst_generator.py:158`

#### 4.3 get_word() 内部实现

**文件**: `difuzz-rtl/Fuzzer/src/inst_generator.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| `inst_generator.py:164` | `opcode = random.choice(self.opcodes)` | 随机选择操作码 |
| `inst_generator.py:172` | `(syntax, xregs, fregs, imms, symbols) = self.opcodes_map.get(opcode)` | 获取指令语法和操作数 |
| `inst_generator.py:185` | `(tpe, insts) = key_word(opcode, syntax, xregs, fregs, imms, symbols)` | 调用指令生成函数 |

> **跨文件调用说明**:
> - **调用位置**: `inst_generator.py:185`
> - **调用的函数**: `key_word` (如 `word_jal`, `word_branch` 等)
> - **函数定义位置**: `word.py:95` ~ `word.py:236` (多个函数)

| 行号 | 代码 | 说明 |
|------|------|------|
| `inst_generator.py:188` | `word = Word(label_num, insts, tpe, xregs, fregs, imms, symbols)` | 创建 Word 对象 |

> **跨文件调用说明**:
> - **调用位置**: `inst_generator.py:188`
> - **调用的类**: `Word`
> - **类定义位置**: `word.py:18`

#### 4.4 填充指令操作数 populate_word()

**调用位置**: `mutator.py:409`
```python
self.inst_generator.populate_word(word, len(prefix), PREFIX)
```

**函数定义位置**: `inst_generator.py:192`

| 行号 | 代码 | 说明 |
|------|------|------|
| `inst_generator.py:201` | `for xreg in word.xregs:` | 遍历通用寄存器操作数 |
| `inst_generator.py:203` | `opvals[xreg] = self._get_xregs()` | 获取寄存器编号 |
| `inst_generator.py:207` | `for freg in word.fregs:` | 遍历浮点寄存器操作数 |
| `inst_generator.py:210` | `for (imm, align) in word.imms:` | 遍历立即数操作数 |
| `inst_generator.py:213` | `for symbol in word.symbols:` | 遍历符号操作数 |
| `inst_generator.py:216` | `word.populate(opvals, part)` | 填充指令 |

> **跨文件调用说明**:
> - **调用位置**: `inst_generator.py:216`
> - **调用的方法**: `word.populate()`
> - **方法定义位置**: `word.py:40`

#### 4.5 创建 simInput 对象

| 行号 | 代码 | 说明 |
|------|------|------|
| `mutator.py:433` | `sim_input = simInput(prefix, words, suffix, ints, data_seed, template)` | 创建测试输入对象 |

> **跨文件调用说明**:
> - **调用位置**: `mutator.py:433`
> - **调用的类**: `simInput`
> - **类定义位置**: `mutator.py:24`

---

### Step 5: 预处理 preprocessor.process()

**调用位置**: `Fuzzer.py:60`
```python
(isa_input, rtl_input, symbols) = preprocessor.process(sim_input, data, assert_intr)
```

**函数定义位置**: `preprocessor.py:57`

#### 5.1 提取指令信息

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:85` | `prefix_insts = sim_input.get_prefix()` | 获取前缀指令列表 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:85`
> - **调用的方法**: `sim_input.get_prefix()`
> - **方法定义位置**: `mutator.py:68`

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:86` | `insts = sim_input.get_insts()` | 获取主指令列表 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:86`
> - **调用的方法**: `sim_input.get_insts()`
> - **方法定义位置**: `mutator.py:76`

#### 5.2 生成汇编文件

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:99` | `sim_input.save(si_name, data)` | 保存测试输入 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:99`
> - **调用的方法**: `sim_input.save()`
> - **方法定义位置**: `mutator.py:38`

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:101` | `fd = open(test_template, 'r')` | 打开测试模板 |
| `preprocessor.py:108` | `if '_fuzz_prefix:' in line:` | 查找前缀插入点 |
| `preprocessor.py:109` | `for inst in prefix_insts:` | 插入前缀指令 |
| `preprocessor.py:112` | `if '_fuzz_main:' in line:` | 查找主指令插入点 |
| `preprocessor.py:113` | `for inst in insts:` | 插入主指令 |
| `preprocessor.py:134` | `fd = open(asm_name, 'w')` | 打开汇编文件 |
| `preprocessor.py:135` | `fd.writelines(assembly)` | 写入汇编代码 |

#### 5.3 编译生成 ELF 和 HEX

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:138` | `cc_args = self.cc_args + extra_args + [ asm_name, '-o', elf_name ]` | 构建编译参数 |
| `preprocessor.py:142` | `cc_ret = subprocess.call(cc_args)` | 调用 GCC 编译 |
| `preprocessor.py:149` | `elf2hex_args = self.elf2hex_args + [ elf_name, '--output', hex_name]` | 构建 elf2hex 参数 |
| `preprocessor.py:150` | `subprocess.call(elf2hex_args)` | 调用 elf2hex |
| `preprocessor.py:151` | `symbols = self.get_symbols(elf_name, sym_name)` | 提取符号表 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:151`
> - **调用的方法**: `self.get_symbols()`
> - **方法定义位置**: `preprocessor.py:26`

#### 5.4 创建输入对象

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:165` | `isa_input = isaInput(elf_name, isa_intr_name)` | 创建 ISA 输入对象 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:165`
> - **调用的类**: `isaInput`
> - **类定义位置**: `ISASim/host.py:5`

| 行号 | 代码 | 说明 |
|------|------|------|
| `preprocessor.py:166` | `rtl_input = rtlInput(hex_name, rtl_intr_name, data, symbols, max_cycles)` | 创建 RTL 输入对象 |

> **跨文件调用说明**:
> - **调用位置**: `preprocessor.py:166`
> - **调用的类**: `rtlInput`
> - **类定义位置**: `RTLSim/host.py:16`

---

### Step 6: ISA 模拟执行 run_isa_test()

**调用位置**: `Fuzzer.py:63`
```python
ret = run_isa_test(isaHost, isa_input, stop, out, proc_num)
```

**函数定义位置**: `utils.py:52`

| 行号 | 代码 | 说明 |
|------|------|------|
| `utils.py:55` | `timer = Timer(ISA_TIME_LIMIT, isa_timeout, [out, stop, proc_num])` | 创建超时定时器 |
| `utils.py:56` | `timer.start()` | 启动定时器 |
| `utils.py:57` | `isa_ret = isaHost.run_test(isa_input, assert_intr)` | 执行 ISA 测试 |

> **跨文件调用说明**:
> - **调用位置**: `utils.py:57`
> - **调用点所属对象**: `isaHost` (类型: `rvISAhost`)
> - **调用的方法**: `run_test()`
> - **方法定义位置**: `ISASim/host.py:22`

#### 6.1 rvISAhost.run_test() 实现

**文件**: `difuzz-rtl/Fuzzer/ISASim/host.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| `ISASim/host.py:23` | `binary = isa_input.binary` | 获取二进制文件路径 |
| `ISASim/host.py:27` | `args = [ self.spike ] + self.spike_args + intr + ...` | 构建命令行参数 |
| `ISASim/host.py:31` | `return subprocess.call(args)` | 调用 Spike 模拟器 |

---

### Step 7: RTL 模拟执行 rtlHost.run_test()

**调用位置**: `Fuzzer.py:68`
```python
(ret, coverage) = yield rtlHost.run_test(rtl_input, assert_intr)
```

**函数定义位置**: `RTLSim/host.py:111`

#### 7.1 加载测试程序

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:115` | `fd = open(rtl_input.hexfile, 'r')` | 打开 HEX 文件 |
| `RTLSim/host.py:116` | `lines = fd.readlines()` | 读取所有行 |
| `RTLSim/host.py:125` | `(bootrom_addrs, memory) = self.set_bootrom()` | 设置启动 ROM |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:125`
> - **调用的方法**: `self.set_bootrom()`
> - **方法定义位置**: `RTLSim/host.py:46`

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:126` | `for (i, addr) in enumerate(range(_start, _end + 36, 8)):` | 遍历内存地址 |
| `RTLSim/host.py:127` | `memory[addr] = int(lines[i], 16)` | 加载程序到内存 |

#### 7.2 加载中断配置

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:152` | `if assert_intr:` | 判断是否需要中断 |
| `RTLSim/host.py:153` | `fd = open(rtl_input.intrfile, 'r')` | 打开中断配置文件 |
| `RTLSim/host.py:157` | `for pair in intr_pairs:` | 遍历中断配置 |
| `RTLSim/host.py:158` | `ints[int(pair[0], 16)] = int(pair[1], 2)` | 解析中断配置 |

#### 7.3 启动模拟

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:160` | `clk = self.dut.clock` | 获取时钟信号 |
| `RTLSim/host.py:161` | `clk_driver = cocotb.fork(self.clock_gen(clk))` | 启动时钟生成 |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:161`
> - **调用的方法**: `self.clock_gen()`
> - **方法定义位置**: `RTLSim/host.py:73`

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:164` | `yield self.reset(clk, self.dut.metaReset, self.dut.reset)` | 执行复位 |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:164`
> - **调用的方法**: `self.reset()`
> - **方法定义位置**: `RTLSim/host.py:81`

#### 7.4 启动适配器

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:166` | `self.adapter.start(memory, ints)` | 启动 TileLink 适配器 |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:166`
> - **调用点所属对象**: `self.adapter` (类型: `tileAdapter`)
> - **调用的方法**: `start()`
> - **方法定义位置**: `RTLSim/src/adapters/tile_adapter.py:111`

##### 7.4.1 tileAdapter.start() 实现

**文件**: `difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| `tile_adapter.py:115` | `self.drive = True` | 设置驱动标志 |
| `tile_adapter.py:116` | `self.tl_adapter.start(memory)` | 启动 TileLink 适配器 |

> **跨文件调用说明**:
> - **调用位置**: `tile_adapter.py:116`
> - **调用的方法**: `self.tl_adapter.start()`
> - **方法定义位置**: `RTLSim/src/adapters/tilelink/adapter.py` (TileLink 协议适配器)

| 行号 | 代码 | 说明 |
|------|------|------|
| `tile_adapter.py:117` | `self.intr_handler = cocotb.fork(self.interrupt_handler(ints))` | 启动中断处理协程 |

> **跨文件调用说明**:
> - **调用位置**: `tile_adapter.py:117`
> - **调用的方法**: `self.interrupt_handler()`
> - **方法定义位置**: `tile_adapter.py:91`

#### 7.5 运行测试循环

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:167` | `for i in range(max_cycles):` | 最大循环次数 |
| `RTLSim/host.py:168` | `yield clkedge` | 等待时钟边沿 |
| `RTLSim/host.py:170` | `if i % 100 == 0:` | 每 100 周期检查一次 |
| `RTLSim/host.py:171` | `tohost = memory[tohost_addr]` | 读取 tohost 值 |
| `RTLSim/host.py:175` | `self.adapter.probe_tohost(tohost_addr)` | 探测 tohost 地址 |

#### 7.6 停止模拟并保存签名

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:177` | `yield self.adapter.stop()` | 停止适配器 |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:177`
> - **调用的方法**: `self.adapter.stop()`
> - **方法定义位置**: `tile_adapter.py:120`

| 行号 | 代码 | 说明 |
|------|------|------|
| `RTLSim/host.py:197` | `self.save_signature(memory, sig_start, sig_end, data_addrs, self.rtl_sig_file)` | 保存签名 |

> **跨文件调用说明**:
> - **调用位置**: `RTLSim/host.py:197`
> - **调用的方法**: `self.save_signature()`
> - **方法定义位置**: `RTLSim/host.py:93`

---

### Step 8: 结果比较 checker.check()

**调用位置**: `Fuzzer.py:85`
```python
match = checker.check(symbols)
```

**函数定义位置**: `signature_checker.py:114`

#### 8.1 读取符号位置

| 行号 | 代码 | 说明 |
|------|------|------|
| `signature_checker.py:116` | `(xreg_idxes, freg_idxes, csr_idxes, data_symbols, data_idx_start) = self.read_symbols(symbols)` | 读取符号索引 |

> **跨文件调用说明**:
> - **调用位置**: `signature_checker.py:116`
> - **调用的方法**: `self.read_symbols()`
> - **方法定义位置**: `signature_checker.py:19`

#### 8.2 读取签名文件

| 行号 | 代码 | 说明 |
|------|------|------|
| `signature_checker.py:119` | `(isa_xreg_vals, isa_freg_vals, isa_csr_vals, isa_data_vals) = self.read_sig(self.isa_sigfile, ...)` | 读取 ISA 签名 |

> **跨文件调用说明**:
> - **调用位置**: `signature_checker.py:119`
> - **调用的方法**: `self.read_sig()`
> - **方法定义位置**: `signature_checker.py:41`

| 行号 | 代码 | 说明 |
|------|------|------|
| `signature_checker.py:123` | `(rtl_xreg_vals, rtl_freg_vals, rtl_csr_vals, rtl_data_vals) = self.read_sig(self.rtl_sigfile, ...)` | 读取 RTL 签名 |

#### 8.3 比较寄存器

| 行号 | 代码 | 说明 |
|------|------|------|
| `signature_checker.py:132` | `for (i, val) in enumerate(zip(isa_xreg_vals, rtl_xreg_vals)):` | 遍历通用寄存器 |
| `signature_checker.py:133` | `match = (val[0] == val[1])` | 比较 ISA 和 RTL 值 |
| `signature_checker.py:138` | `for (i, val) in enumerate(zip(isa_freg_vals, rtl_freg_vals)):` | 遍历浮点寄存器 |
| `signature_checker.py:144` | `for csr_name in csr_names:` | 遍历 CSR 寄存器 |

#### 8.4 比较内存数据

| 行号 | 代码 | 说明 |
|------|------|------|
| `signature_checker.py:153` | `for i in range(6):` | 遍历 6 个数据段 |
| `signature_checker.py:158` | `if isa_data != rtl_data:` | 比较数据是否一致 |
| `signature_checker.py:170` | `return (xreg_match & freg_match & csr_match & data_match)` | 返回比较结果 |

---

### Step 9: 覆盖率引导

#### 9.1 检查覆盖率增长

**文件**: `Fuzzer.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| `Fuzzer.py:112` | `if coverage > last_coverage:` | 检查覆盖率是否增长 |

#### 9.2 保存覆盖日志

| 行号 | 代码 | 说明 |
|------|------|------|
| `Fuzzer.py:118` | `save_file(cov_log, 'a', ...)` | 保存覆盖率日志 |

> **跨文件调用说明**:
> - **调用位置**: `Fuzzer.py:118`
> - **调用的函数**: `save_file()`
> - **函数定义位置**: `utils.py:76`

#### 9.3 添加到语料库

| 行号 | 代码 | 说明 |
|------|------|------|
| `Fuzzer.py:121` | `sim_input.save(out + '/corpus/id_{}.si'.format(cNum))` | 保存测试用例 |

> **跨文件调用说明**:
> - **调用位置**: `Fuzzer.py:121`
> - **调用的方法**: `sim_input.save()`
> - **方法定义位置**: `mutator.py:38`

| 行号 | 代码 | 说明 |
|------|------|------|
| `Fuzzer.py:124` | `mutator.add_corpus(sim_input)` | 添加到变异器语料库 |

> **跨文件调用说明**:
> - **调用位置**: `Fuzzer.py:124`
> - **调用的方法**: `mutator.add_corpus()`
> - **方法定义位置**: `mutator.py:450`

#### 9.4 更新变异阶段

| 行号 | 代码 | 说明 |
|------|------|------|
| `Fuzzer.py:127` | `mutator.update_phase(it)` | 更新变异阶段 |

> **跨文件调用说明**:
> - **调用位置**: `Fuzzer.py:127`
> - **调用的方法**: `mutator.update_phase()`
> - **方法定义位置**: `mutator.py:438`

##### 9.4.1 update_phase() 实现

**文件**: `mutator.py:438`

| 行号 | 代码 | 说明 |
|------|------|------|
| `mutator.py:439` | `if it < self.corpus_size / 10 or self.no_guide:` | 判断是否在初始化阶段 |
| `mutator.py:440` | `self.phase = GENERATION` | 设置为生成阶段 |
| `mutator.py:443` | `if rand < 0.1:` | 10% 概率生成 |
| `mutator.py:444` | `self.phase = GENERATION` | |
| `mutator.py:445` | `elif rand < 0.55:` | 45% 概率变异 |
| `mutator.py:446` | `self.phase = MUTATION` | |
| `mutator.py:448` | `self.phase = MERGE` | 45% 概率合并 |

---

## 3. 完整跨文件调用关系图

```
DifuzzRTL.py (入口)
    │
    ├──► Fuzzer.py:12 (Run 协程)
    │       │
    │       ├──► utils.py:92 (setup)
    │       │       ├──► mutator.py:93 (rvMutator)
    │       │       ├──► preprocessor.py:10 (rvPreProcessor)
    │       │       ├──► ISASim/host.py:10 (rvISAhost)
    │       │       ├──► RTLSim/host.py:24 (rvRTLhost)
    │       │       │       └──► tile_adapter.py:22 (tileAdapter)
    │       │       │               └──► tilelink/adapter.py (tlAdapter)
    │       │       └──► signature_checker.py:5 (sigChecker)
    │       │
    │       ├──► mutator.py:356 (get)
    │       │       ├──► inst_generator.py:158 (get_word)
    │       │       │       ├──► word.py:18 (Word)
    │       │       │       └──► word.py:95-236 (word_* 函数)
    │       │       └──► inst_generator.py:192 (populate_word)
    │       │               └──► word.py:40 (populate)
    │       │
    │       ├──► preprocessor.py:57 (process)
    │       │       ├──► mutator.py:68 (get_prefix)
    │       │       ├──► mutator.py:76 (get_insts)
    │       │       ├──► mutator.py:38 (save)
    │       │       ├──► preprocessor.py:26 (get_symbols)
    │       │       ├──► ISASim/host.py:5 (isaInput)
    │       │       └──► RTLSim/host.py:16 (rtlInput)
    │       │
    │       ├──► utils.py:52 (run_isa_test)
    │       │       └──► ISASim/host.py:22 (run_test)
    │       │
    │       ├──► RTLSim/host.py:111 (run_test)
    │       │       ├──► RTLSim/host.py:46 (set_bootrom)
    │       │       ├──► RTLSim/host.py:73 (clock_gen)
    │       │       ├──► RTLSim/host.py:81 (reset)
    │       │       ├──► tile_adapter.py:111 (start)
    │       │       │       └──► tilelink/adapter.py (start)
    │       │       ├──► tile_adapter.py:91 (interrupt_handler)
    │       │       ├──► tile_adapter.py:105 (probe_tohost)
    │       │       ├──► tile_adapter.py:120 (stop)
    │       │       └──► RTLSim/host.py:93 (save_signature)
    │       │
    │       ├──► signature_checker.py:114 (check)
    │       │       ├──► signature_checker.py:19 (read_symbols)
    │       │       └──► signature_checker.py:41 (read_sig)
    │       │
    │       ├──► utils.py:76 (save_file)
    │       ├──► mutator.py:38 (save)
    │       ├──► mutator.py:450 (add_corpus)
    │       └──► mutator.py:438 (update_phase)
    │
    └──► Minimizer.py:14 (Minimize) [可选]
```

---

## 4. 文件索引

| 文件路径 | 主要功能 |
|---------|---------|
| `difuzz-rtl/Fuzzer/DifuzzRTL.py` | 程序入口，参数解析，模式选择 |
| `difuzz-rtl/Fuzzer/Fuzzer.py` | 主模糊测试循环 Run() |
| `difuzz-rtl/Fuzzer/Minimizer.py` | 测试用例最小化 |
| `difuzz-rtl/Fuzzer/src/utils.py` | 工具函数，setup() 初始化 |
| `difuzz-rtl/Fuzzer/src/mutator.py` | 指令变异器 rvMutator，测试输入 simInput |
| `difuzz-rtl/Fuzzer/src/inst_generator.py` | 指令生成器 rvInstGenerator |
| `difuzz-rtl/Fuzzer/src/word.py` | 指令字 Word 类，word_* 生成函数 |
| `difuzz-rtl/Fuzzer/src/preprocessor.py` | 预处理器 rvPreProcessor |
| `difuzz-rtl/Fuzzer/src/signature_checker.py` | 签名检查器 sigChecker |
| `difuzz-rtl/Fuzzer/src/multicore_manager.py` | 多核进程管理器 procManager |
| `difuzz-rtl/Fuzzer/src/riscv_definitions.py` | RISC-V 指令定义 |
| `difuzz-rtl/Fuzzer/ISASim/host.py` | ISA 模拟器接口 rvISAhost |
| `difuzz-rtl/Fuzzer/RTLSim/host.py` | RTL 模拟器接口 rvRTLhost |
| `difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py` | Tile 适配器 tileAdapter |
