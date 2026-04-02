# Difuzz-RTL 执行流程分析报告

## 1. 执行流程图

<pre>
┌─────────────────────────────────────────────────────────────────────────────┐
│                              程序启动                                        │
│              difuzz-rtl/Fuzzer/DifuzzRTL.py (入口文件)                        │
│              通过 TestFactory(Run) 调用 <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L12">difuzz-rtl/Fuzzer/Fuzzer.py:12</a> (Run 协程)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: 组件初始化 setup()                                                 │
│  ├─ 调用位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L23">difuzz-rtl/Fuzzer/Fuzzer.py:23</a>                                                  │
│  ├─ 定义位置: <a href="difuzz-rtl/Fuzzer/src/utils.py#L92">difuzz-rtl/Fuzzer/src/utils.py:92</a>                                                   │
│  └─ 调用链:                                                                  │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/utils.py#L93">difuzz-rtl/Fuzzer/src/utils.py:93</a>  → <a href="difuzz-rtl/Fuzzer/src/mutator.py#L93">difuzz-rtl/Fuzzer/src/mutator.py:93</a>      (rvMutator)                       │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/utils.py#L97">difuzz-rtl/Fuzzer/src/utils.py:97</a>  → <a href="difuzz-rtl/Fuzzer/src/preprocessor.py#L10">difuzz-rtl/Fuzzer/src/preprocessor.py:10</a> (rvPreProcessor)                  │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/utils.py#L106">difuzz-rtl/Fuzzer/src/utils.py:106</a> → <a href="difuzz-rtl/Fuzzer/ISASim/host.py#L10">difuzz-rtl/Fuzzer/ISASim/host.py:10</a>  (rvISAhost)                       │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/utils.py#L107">difuzz-rtl/Fuzzer/src/utils.py:107</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L24">difuzz-rtl/Fuzzer/RTLSim/host.py:24</a>  (rvRTLhost)                       │
│      └─ <a href="difuzz-rtl/Fuzzer/src/utils.py#L109">difuzz-rtl/Fuzzer/src/utils.py:109</a> → <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L5">difuzz-rtl/Fuzzer/src/signature_checker.py:5</a> (sigChecker)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 2: 主循环 Run() 开始                                                  │
│  ├─ 定义位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L12">difuzz-rtl/Fuzzer/Fuzzer.py:12</a>                                                  │
│  ├─ 循环开始: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L39">difuzz-rtl/Fuzzer/Fuzzer.py:39</a>                                                  │
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
        │ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L53">difuzz-rtl/Fuzzer/Fuzzer.py:53</a>      │              │ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L60">difuzz-rtl/Fuzzer/Fuzzer.py:60</a>      │
        │                   │              │                   │
        │ mutator.get()     │              │ preprocessor.     │
        │ 定义位置:          │              │ process()         │
        │ <a href="difuzz-rtl/Fuzzer/src/mutator.py#L356">difuzz-rtl/Fuzzer/src/mutator.py:356</a>    │              │ 定义位置:          │
        │                   │              │ <a href="difuzz-rtl/Fuzzer/src/preprocessor.py#L57">difuzz-rtl/Fuzzer/src/preprocessor.py:57</a>│
        └───────────────────┘              └─────────┬─────────┘
                                                      │
                    ┌─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 5: ISA 模拟执行                                                       │
│  ├─ 调用位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L63">difuzz-rtl/Fuzzer/Fuzzer.py:63</a>                                                  │
│  ├─ 调用函数: run_isa_test()                                                │
│  ├─ 定义位置: <a href="difuzz-rtl/Fuzzer/src/utils.py#L52">difuzz-rtl/Fuzzer/src/utils.py:52</a>                                                   │
│  └─ 内部调用: <a href="difuzz-rtl/Fuzzer/src/utils.py#L57">difuzz-rtl/Fuzzer/src/utils.py:57</a> → <a href="difuzz-rtl/Fuzzer/ISASim/host.py#L22">difuzz-rtl/Fuzzer/ISASim/host.py:22</a> (isaHost.run_test)            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 6: RTL 模拟执行                                                       │
│  ├─ 调用位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L68">difuzz-rtl/Fuzzer/Fuzzer.py:68</a>                                                  │
│  ├─ 调用方法: rtlHost.run_test()                                            │
│  ├─ 定义位置: <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L111">difuzz-rtl/Fuzzer/RTLSim/host.py:111</a>                                            │
│  └─ 内部调用链:                                                              │
│      ├─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L125">difuzz-rtl/Fuzzer/RTLSim/host.py:125</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L46">difuzz-rtl/Fuzzer/RTLSim/host.py:46</a> (set_bootrom)                │
│      ├─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L164">difuzz-rtl/Fuzzer/RTLSim/host.py:164</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L81">difuzz-rtl/Fuzzer/RTLSim/host.py:81</a> (reset)                      │
│      ├─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L166">difuzz-rtl/Fuzzer/RTLSim/host.py:166</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L111">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:111</a> (adapter.start)            │
│      ├─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L175">difuzz-rtl/Fuzzer/RTLSim/host.py:175</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L105">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:105</a> (probe_tohost)             │
│      ├─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L177">difuzz-rtl/Fuzzer/RTLSim/host.py:177</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L120">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:120</a> (adapter.stop)             │
│      └─ <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L197">difuzz-rtl/Fuzzer/RTLSim/host.py:197</a> → <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L93">difuzz-rtl/Fuzzer/RTLSim/host.py:93</a> (save_signature)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 7: 结果比较 checker.check()                                           │
│  ├─ 调用位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L85">difuzz-rtl/Fuzzer/Fuzzer.py:85</a>                                                  │
│  ├─ 定义位置: <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L114">difuzz-rtl/Fuzzer/src/signature_checker.py:114</a>                                      │
│  └─ 内部调用:                                                                │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L116">difuzz-rtl/Fuzzer/src/signature_checker.py:116</a> → :19 (read_symbols)                       │
│      ├─ <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L119">difuzz-rtl/Fuzzer/src/signature_checker.py:119</a> → :41 (read_sig ISA)                       │
│      └─ <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L123">difuzz-rtl/Fuzzer/src/signature_checker.py:123</a> → :41 (read_sig RTL)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
        ┌───────────────────┐              ┌───────────────────┐
        │    Match          │              │    Mismatch       │
        │    继续循环       │              │    保存用例       │
        │                   │              │                   │
        │ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L84-L85">difuzz-rtl/Fuzzer/Fuzzer.py:84-85</a>   │              │ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L95-L110">difuzz-rtl/Fuzzer/Fuzzer.py:95-110</a>  │
        │ if ret == SUCCESS │              │ if not match:     │
        └───────────────────┘              └───────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 8: 覆盖率引导 (若覆盖率增长)                                          │
│  ├─ 调用位置: <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L112">difuzz-rtl/Fuzzer/Fuzzer.py:112</a> (if coverage > last_coverage)                   │
│  └─ 调用链:                                                                  │
│      ├─ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L118">difuzz-rtl/Fuzzer/Fuzzer.py:118</a> → <a href="difuzz-rtl/Fuzzer/src/utils.py#L76">difuzz-rtl/Fuzzer/src/utils.py:76</a> (save_file)                             │
│      ├─ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L121">difuzz-rtl/Fuzzer/Fuzzer.py:121</a> → <a href="difuzz-rtl/Fuzzer/src/mutator.py#L38">difuzz-rtl/Fuzzer/src/mutator.py:38</a> (sim_input.save)                      │
│      ├─ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L124">difuzz-rtl/Fuzzer/Fuzzer.py:124</a> → <a href="difuzz-rtl/Fuzzer/src/mutator.py#L450">difuzz-rtl/Fuzzer/src/mutator.py:450</a> (mutator.add_corpus)                │
│      └─ <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L127">difuzz-rtl/Fuzzer/Fuzzer.py:127</a> → <a href="difuzz-rtl/Fuzzer/src/mutator.py#L438">difuzz-rtl/Fuzzer/src/mutator.py:438</a> (mutator.update_phase)              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │  下一轮循环   │
                              │  it += 1      │
                              │  <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L39">difuzz-rtl/Fuzzer/Fuzzer.py:39</a> │
                              └───────────────┘
</pre>

---

## 2. 详细执行流程（按顺序）

### Step 1: 程序入口 - 参数解析

**文件**: `difuzz-rtl/Fuzzer/DifuzzRTL.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:41](difuzz-rtl/Fuzzer/DifuzzRTL.py#L41) | `parser = envParser()` | 创建环境变量解析器 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:43](difuzz-rtl/Fuzzer/DifuzzRTL.py#L43) | `parser.add_option('toplevel', ...)` | 添加 toplevel 参数 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:44](difuzz-rtl/Fuzzer/DifuzzRTL.py#L44) | `parser.add_option('num_iter', ...)` | 添加迭代次数参数 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:46](difuzz-rtl/Fuzzer/DifuzzRTL.py#L46) | `parser.add_option('template', ...)` | 添加模板参数 |

**创建输出目录**:

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:74](difuzz-rtl/Fuzzer/DifuzzRTL.py#L74) | `os.makedirs(out + '/mismatch')` | 创建 mismatch 目录 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:86](difuzz-rtl/Fuzzer/DifuzzRTL.py#L86) | `os.makedirs(out + '/corpus')` | 创建 corpus 目录 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:89](difuzz-rtl/Fuzzer/DifuzzRTL.py#L89) | `datetime.today().strftime(...)` | 获取当前日期 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:90](difuzz-rtl/Fuzzer/DifuzzRTL.py#L90) | `cov_log = out + '/cov_log_{}.txt'` | 设置覆盖率日志文件名 |

---

### Step 2: 选择执行模式

**文件**: `difuzz-rtl/Fuzzer/DifuzzRTL.py`

#### 单核模式

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:97](difuzz-rtl/Fuzzer/DifuzzRTL.py#L97) | `if not multicore:` | 判断是否单核模式 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:98](difuzz-rtl/Fuzzer/DifuzzRTL.py#L98) | `if minimize:` | 判断是否最小化模式 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:106](difuzz-rtl/Fuzzer/DifuzzRTL.py#L106) | `factory = TestFactory(Run)` | 创建 Run 测试工厂 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:111](difuzz-rtl/Fuzzer/DifuzzRTL.py#L111) | `factory.generate_tests()` | 生成测试 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/DifuzzRTL.py:106](difuzz-rtl/Fuzzer/DifuzzRTL.py#L106)
> - **调用的函数**: `Run` 协程
> - **函数定义位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:12](difuzz-rtl/Fuzzer/Fuzzer.py#L12)

#### 多核模式

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:113](difuzz-rtl/Fuzzer/DifuzzRTL.py#L113) | `else:` | 多核模式分支 |
| [difuzz-rtl/Fuzzer/DifuzzRTL.py:114](difuzz-rtl/Fuzzer/DifuzzRTL.py#L114) | `manager = procManager(multicore, out, date)` | 创建进程管理器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/DifuzzRTL.py:114](difuzz-rtl/Fuzzer/DifuzzRTL.py#L114)
> - **调用的类**: `procManager`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/multicore_manager.py:38](difuzz-rtl/Fuzzer/src/multicore_manager.py#L38)

---

### Step 3: 组件初始化 setup()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:23](difuzz-rtl/Fuzzer/Fuzzer.py#L23)
<pre>
(mutator, preprocessor, isaHost, rtlHost, checker) = \
    setup(dut, toplevel, template, out, proc_num, debug, no_guide=no_guide)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/utils.py:92](difuzz-rtl/Fuzzer/src/utils.py#L92)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:93](difuzz-rtl/Fuzzer/src/utils.py#L93) | `mutator = rvMutator(no_guide=no_guide)` | 创建指令变异器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:93](difuzz-rtl/Fuzzer/src/utils.py#L93)
> - **调用的类**: `rvMutator`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:93](difuzz-rtl/Fuzzer/src/mutator.py#L93)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:97](difuzz-rtl/Fuzzer/src/utils.py#L97) | `preprocessor = rvPreProcessor(cc, elf2hex, template, out, proc_num)` | 创建预处理器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:97](difuzz-rtl/Fuzzer/src/utils.py#L97)
> - **调用的类**: `rvPreProcessor`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:10](difuzz-rtl/Fuzzer/src/preprocessor.py#L10)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:106](difuzz-rtl/Fuzzer/src/utils.py#L106) | `isaHost = rvISAhost(spike, spike_arg, isa_sigfile)` | 创建 ISA 模拟器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:106](difuzz-rtl/Fuzzer/src/utils.py#L106)
> - **调用的类**: `rvISAhost`
> - **类定义位置**: [difuzz-rtl/Fuzzer/ISASim/host.py:10](difuzz-rtl/Fuzzer/ISASim/host.py#L10)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:107](difuzz-rtl/Fuzzer/src/utils.py#L107) | `rtlHost = rvRTLhost(dut, toplevel, rtl_sigfile, debug=debug)` | 创建 RTL 模拟器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:107](difuzz-rtl/Fuzzer/src/utils.py#L107)
> - **调用的类**: `rvRTLhost`
> - **类定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:24](difuzz-rtl/Fuzzer/RTLSim/host.py#L24)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:109](difuzz-rtl/Fuzzer/src/utils.py#L109) | `checker = sigChecker(isa_sigfile, rtl_sigfile, debug, minimizing)` | 创建签名检查器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:109](difuzz-rtl/Fuzzer/src/utils.py#L109)
> - **调用的类**: `sigChecker`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:5](difuzz-rtl/Fuzzer/src/signature_checker.py#L5)

---

### Step 4: 生成测试输入 mutator.get()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:53](difuzz-rtl/Fuzzer/Fuzzer.py#L53)
<pre>
(sim_input, data) = mutator.get(assert_intr)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:356](difuzz-rtl/Fuzzer/src/mutator.py#L356)

#### 4.1 确定变异阶段

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/mutator.py:366](difuzz-rtl/Fuzzer/src/mutator.py#L366) | `if self.phase == GENERATION:` | 判断是否为生成阶段 |
| [difuzz-rtl/Fuzzer/src/mutator.py:377](difuzz-rtl/Fuzzer/src/mutator.py#L377) | `elif self.phase in [ MUTATION, MERGE ]:` | 判断是否为变异或合并阶段 |

#### 4.2 GENERATION 阶段 - 生成指令

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/mutator.py:367](difuzz-rtl/Fuzzer/src/mutator.py#L367) | `for n in range(self.num_prefix):` | 循环生成前缀指令 |
| [difuzz-rtl/Fuzzer/src/mutator.py:368](difuzz-rtl/Fuzzer/src/mutator.py#L368) | `word = self.inst_generator.get_word(PREFIX)` | 获取一个前缀指令字 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/mutator.py:368](difuzz-rtl/Fuzzer/src/mutator.py#L368)
> - **调用点所属对象**: `self.inst_generator` (类型: `rvInstGenerator`)
> - **调用的方法**: `get_word()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:158](difuzz-rtl/Fuzzer/src/inst_generator.py#L158)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/mutator.py:370](difuzz-rtl/Fuzzer/src/mutator.py#L370) | `for n in range(self.num_words):` | 循环生成主指令 |
| [difuzz-rtl/Fuzzer/src/mutator.py:371](difuzz-rtl/Fuzzer/src/mutator.py#L371) | `word = self.inst_generator.get_word(MAIN)` | 获取一个主指令字 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/mutator.py:371](difuzz-rtl/Fuzzer/src/mutator.py#L371)
> - **调用的方法**: `get_word()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:158](difuzz-rtl/Fuzzer/src/inst_generator.py#L158)

#### 4.3 get_word() 内部实现

**文件**: `difuzz-rtl/Fuzzer/src/inst_generator.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/inst_generator.py:164](difuzz-rtl/Fuzzer/src/inst_generator.py#L164) | `opcode = random.choice(self.opcodes)` | 随机选择操作码 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:172](difuzz-rtl/Fuzzer/src/inst_generator.py#L172) | `(syntax, xregs, fregs, imms, symbols) = self.opcodes_map.get(opcode)` | 获取指令语法和操作数 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:185](difuzz-rtl/Fuzzer/src/inst_generator.py#L185) | `(tpe, insts) = key_word(opcode, syntax, xregs, fregs, imms, symbols)` | 调用指令生成函数 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:185](difuzz-rtl/Fuzzer/src/inst_generator.py#L185)
> - **调用的函数**: `key_word` (如 `word_jal`, `word_branch` 等)
> - **函数定义位置**: [difuzz-rtl/Fuzzer/src/word.py:95](difuzz-rtl/Fuzzer/src/word.py#L95) ~ [difuzz-rtl/Fuzzer/src/word.py:236](difuzz-rtl/Fuzzer/src/word.py#L236) (多个函数)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/inst_generator.py:188](difuzz-rtl/Fuzzer/src/inst_generator.py#L188) | `word = Word(label_num, insts, tpe, xregs, fregs, imms, symbols)` | 创建 Word 对象 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:188](difuzz-rtl/Fuzzer/src/inst_generator.py#L188)
> - **调用的类**: `Word`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/word.py:18](difuzz-rtl/Fuzzer/src/word.py#L18)

#### 4.4 填充指令操作数 populate_word()

**调用位置**: [difuzz-rtl/Fuzzer/src/mutator.py:409](difuzz-rtl/Fuzzer/src/mutator.py#L409)
<pre>
self.inst_generator.populate_word(word, len(prefix), PREFIX)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:192](difuzz-rtl/Fuzzer/src/inst_generator.py#L192)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/inst_generator.py:201](difuzz-rtl/Fuzzer/src/inst_generator.py#L201) | `for xreg in word.xregs:` | 遍历通用寄存器操作数 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:203](difuzz-rtl/Fuzzer/src/inst_generator.py#L203) | `opvals[xreg] = self._get_xregs()` | 获取寄存器编号 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:207](difuzz-rtl/Fuzzer/src/inst_generator.py#L207) | `for freg in word.fregs:` | 遍历浮点寄存器操作数 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:210](difuzz-rtl/Fuzzer/src/inst_generator.py#L210) | `for (imm, align) in word.imms:` | 遍历立即数操作数 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:213](difuzz-rtl/Fuzzer/src/inst_generator.py#L213) | `for symbol in word.symbols:` | 遍历符号操作数 |
| [difuzz-rtl/Fuzzer/src/inst_generator.py:216](difuzz-rtl/Fuzzer/src/inst_generator.py#L216) | `word.populate(opvals, part)` | 填充指令 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/inst_generator.py:216](difuzz-rtl/Fuzzer/src/inst_generator.py#L216)
> - **调用的方法**: `word.populate()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/word.py:40](difuzz-rtl/Fuzzer/src/word.py#L40)

#### 4.5 创建 simInput 对象

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/mutator.py:433](difuzz-rtl/Fuzzer/src/mutator.py#L433) | `sim_input = simInput(prefix, words, suffix, ints, data_seed, template)` | 创建测试输入对象 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/mutator.py:433](difuzz-rtl/Fuzzer/src/mutator.py#L433)
> - **调用的类**: `simInput`
> - **类定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:24](difuzz-rtl/Fuzzer/src/mutator.py#L24)

---

### Step 5: 预处理 preprocessor.process()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:60](difuzz-rtl/Fuzzer/Fuzzer.py#L60)
<pre>
(isa_input, rtl_input, symbols) = preprocessor.process(sim_input, data, assert_intr)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:57](difuzz-rtl/Fuzzer/src/preprocessor.py#L57)

#### 5.1 提取指令信息

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:85](difuzz-rtl/Fuzzer/src/preprocessor.py#L85) | `prefix_insts = sim_input.get_prefix()` | 获取前缀指令列表 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:85](difuzz-rtl/Fuzzer/src/preprocessor.py#L85)
> - **调用的方法**: `sim_input.get_prefix()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:68](difuzz-rtl/Fuzzer/src/mutator.py#L68)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:86](difuzz-rtl/Fuzzer/src/preprocessor.py#L86) | `insts = sim_input.get_insts()` | 获取主指令列表 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:86](difuzz-rtl/Fuzzer/src/preprocessor.py#L86)
> - **调用的方法**: `sim_input.get_insts()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:76](difuzz-rtl/Fuzzer/src/mutator.py#L76)

#### 5.2 生成汇编文件

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:99](difuzz-rtl/Fuzzer/src/preprocessor.py#L99) | `sim_input.save(si_name, data)` | 保存测试输入 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:99](difuzz-rtl/Fuzzer/src/preprocessor.py#L99)
> - **调用的方法**: `sim_input.save()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:38](difuzz-rtl/Fuzzer/src/mutator.py#L38)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:101](difuzz-rtl/Fuzzer/src/preprocessor.py#L101) | `fd = open(test_template, 'r')` | 打开测试模板 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:108](difuzz-rtl/Fuzzer/src/preprocessor.py#L108) | `if '_fuzz_prefix:' in line:` | 查找前缀插入点 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:109](difuzz-rtl/Fuzzer/src/preprocessor.py#L109) | `for inst in prefix_insts:` | 插入前缀指令 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:112](difuzz-rtl/Fuzzer/src/preprocessor.py#L112) | `if '_fuzz_main:' in line:` | 查找主指令插入点 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:113](difuzz-rtl/Fuzzer/src/preprocessor.py#L113) | `for inst in insts:` | 插入主指令 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:134](difuzz-rtl/Fuzzer/src/preprocessor.py#L134) | `fd = open(asm_name, 'w')` | 打开汇编文件 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:135](difuzz-rtl/Fuzzer/src/preprocessor.py#L135) | `fd.writelines(assembly)` | 写入汇编代码 |

#### 5.3 编译生成 ELF 和 HEX

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:138](difuzz-rtl/Fuzzer/src/preprocessor.py#L138) | `cc_args = self.cc_args + extra_args + [ asm_name, '-o', elf_name ]` | 构建编译参数 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:142](difuzz-rtl/Fuzzer/src/preprocessor.py#L142) | `cc_ret = subprocess.call(cc_args)` | 调用 GCC 编译 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:149](difuzz-rtl/Fuzzer/src/preprocessor.py#L149) | `elf2hex_args = self.elf2hex_args + [ elf_name, '--output', hex_name]` | 构建 elf2hex 参数 |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:150](difuzz-rtl/Fuzzer/src/preprocessor.py#L150) | `subprocess.call(elf2hex_args)` | 调用 elf2hex |
| [difuzz-rtl/Fuzzer/src/preprocessor.py:151](difuzz-rtl/Fuzzer/src/preprocessor.py#L151) | `symbols = self.get_symbols(elf_name, sym_name)` | 提取符号表 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:151](difuzz-rtl/Fuzzer/src/preprocessor.py#L151)
> - **调用的方法**: `self.get_symbols()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:26](difuzz-rtl/Fuzzer/src/preprocessor.py#L26)

#### 5.4 创建输入对象

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:165](difuzz-rtl/Fuzzer/src/preprocessor.py#L165) | `isa_input = isaInput(elf_name, isa_intr_name)` | 创建 ISA 输入对象 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:165](difuzz-rtl/Fuzzer/src/preprocessor.py#L165)
> - **调用的类**: `isaInput`
> - **类定义位置**: [difuzz-rtl/Fuzzer/ISASim/host.py:5](difuzz-rtl/Fuzzer/ISASim/host.py#L5)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/preprocessor.py:166](difuzz-rtl/Fuzzer/src/preprocessor.py#L166) | `rtl_input = rtlInput(hex_name, rtl_intr_name, data, symbols, max_cycles)` | 创建 RTL 输入对象 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/preprocessor.py:166](difuzz-rtl/Fuzzer/src/preprocessor.py#L166)
> - **调用的类**: `rtlInput`
> - **类定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:16](difuzz-rtl/Fuzzer/RTLSim/host.py#L16)

---

### Step 6: ISA 模拟执行 run_isa_test()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:63](difuzz-rtl/Fuzzer/Fuzzer.py#L63)
<pre>
ret = run_isa_test(isaHost, isa_input, stop, out, proc_num)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/utils.py:52](difuzz-rtl/Fuzzer/src/utils.py#L52)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/utils.py:55](difuzz-rtl/Fuzzer/src/utils.py#L55) | `timer = Timer(ISA_TIME_LIMIT, isa_timeout, [out, stop, proc_num])` | 创建超时定时器 |
| [difuzz-rtl/Fuzzer/src/utils.py:56](difuzz-rtl/Fuzzer/src/utils.py#L56) | `timer.start()` | 启动定时器 |
| [difuzz-rtl/Fuzzer/src/utils.py:57](difuzz-rtl/Fuzzer/src/utils.py#L57) | `isa_ret = isaHost.run_test(isa_input, assert_intr)` | 执行 ISA 测试 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/utils.py:57](difuzz-rtl/Fuzzer/src/utils.py#L57)
> - **调用点所属对象**: `isaHost` (类型: `rvISAhost`)
> - **调用的方法**: `run_test()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/ISASim/host.py:22](difuzz-rtl/Fuzzer/ISASim/host.py#L22)

#### 6.1 rvISAhost.run_test() 实现

**文件**: `difuzz-rtl/Fuzzer/ISASim/host.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/ISASim/host.py:23](difuzz-rtl/Fuzzer/ISASim/host.py#L23) | `binary = isa_input.binary` | 获取二进制文件路径 |
| [difuzz-rtl/Fuzzer/ISASim/host.py:27](difuzz-rtl/Fuzzer/ISASim/host.py#L27) | `args = [ self.spike ] + self.spike_args + intr + ...` | 构建命令行参数 |
| [difuzz-rtl/Fuzzer/ISASim/host.py:31](difuzz-rtl/Fuzzer/ISASim/host.py#L31) | `return subprocess.call(args)` | 调用 Spike 模拟器 |

---

### Step 7: RTL 模拟执行 rtlHost.run_test()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:68](difuzz-rtl/Fuzzer/Fuzzer.py#L68)
<pre>
(ret, coverage) = yield rtlHost.run_test(rtl_input, assert_intr)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:111](difuzz-rtl/Fuzzer/RTLSim/host.py#L111)

#### 7.1 加载测试程序

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:115](difuzz-rtl/Fuzzer/RTLSim/host.py#L115) | `fd = open(rtl_input.hexfile, 'r')` | 打开 HEX 文件 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:116](difuzz-rtl/Fuzzer/RTLSim/host.py#L116) | `lines = fd.readlines()` | 读取所有行 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:125](difuzz-rtl/Fuzzer/RTLSim/host.py#L125) | `(bootrom_addrs, memory) = self.set_bootrom()` | 设置启动 ROM |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:125](difuzz-rtl/Fuzzer/RTLSim/host.py#L125)
> - **调用的方法**: `self.set_bootrom()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:46](difuzz-rtl/Fuzzer/RTLSim/host.py#L46)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:126](difuzz-rtl/Fuzzer/RTLSim/host.py#L126) | `for (i, addr) in enumerate(range(_start, _end + 36, 8)):` | 遍历内存地址 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:127](difuzz-rtl/Fuzzer/RTLSim/host.py#L127) | `memory[addr] = int(lines[i], 16)` | 加载程序到内存 |

#### 7.2 加载中断配置

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:152](difuzz-rtl/Fuzzer/RTLSim/host.py#L152) | `if assert_intr:` | 判断是否需要中断 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:153](difuzz-rtl/Fuzzer/RTLSim/host.py#L153) | `fd = open(rtl_input.intrfile, 'r')` | 打开中断配置文件 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:157](difuzz-rtl/Fuzzer/RTLSim/host.py#L157) | `for pair in intr_pairs:` | 遍历中断配置 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:158](difuzz-rtl/Fuzzer/RTLSim/host.py#L158) | `ints[int(pair[0], 16)] = int(pair[1], 2)` | 解析中断配置 |

#### 7.3 启动模拟

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:160](difuzz-rtl/Fuzzer/RTLSim/host.py#L160) | `clk = self.dut.clock` | 获取时钟信号 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:161](difuzz-rtl/Fuzzer/RTLSim/host.py#L161) | `clk_driver = cocotb.fork(self.clock_gen(clk))` | 启动时钟生成 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:161](difuzz-rtl/Fuzzer/RTLSim/host.py#L161)
> - **调用的方法**: `self.clock_gen()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:73](difuzz-rtl/Fuzzer/RTLSim/host.py#L73)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:164](difuzz-rtl/Fuzzer/RTLSim/host.py#L164) | `yield self.reset(clk, self.dut.metaReset, self.dut.reset)` | 执行复位 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:164](difuzz-rtl/Fuzzer/RTLSim/host.py#L164)
> - **调用的方法**: `self.reset()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:81](difuzz-rtl/Fuzzer/RTLSim/host.py#L81)

#### 7.4 启动适配器

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:166](difuzz-rtl/Fuzzer/RTLSim/host.py#L166) | `self.adapter.start(memory, ints)` | 启动 TileLink 适配器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:166](difuzz-rtl/Fuzzer/RTLSim/host.py#L166)
> - **调用点所属对象**: `self.adapter` (类型: `tileAdapter`)
> - **调用的方法**: `start()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:111](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L111)

##### 7.4.1 tileAdapter.start() 实现

**文件**: `difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:115](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L115) | `self.drive = True` | 设置驱动标志 |
| [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:116](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L116) | `self.tl_adapter.start(memory)` | 启动 TileLink 适配器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:116](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L116)
> - **调用的方法**: `self.tl_adapter.start()`
> - **方法定义位置**: `RTLSim/src/adapters/tilelink/adapter.py` (TileLink 协议适配器)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:117](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L117) | `self.intr_handler = cocotb.fork(self.interrupt_handler(ints))` | 启动中断处理协程 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:117](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L117)
> - **调用的方法**: `self.interrupt_handler()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:91](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L91)

#### 7.5 运行测试循环

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:167](difuzz-rtl/Fuzzer/RTLSim/host.py#L167) | `for i in range(max_cycles):` | 最大循环次数 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:168](difuzz-rtl/Fuzzer/RTLSim/host.py#L168) | `yield clkedge` | 等待时钟边沿 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:170](difuzz-rtl/Fuzzer/RTLSim/host.py#L170) | `if i % 100 == 0:` | 每 100 周期检查一次 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:171](difuzz-rtl/Fuzzer/RTLSim/host.py#L171) | `tohost = memory[tohost_addr]` | 读取 tohost 值 |
| [difuzz-rtl/Fuzzer/RTLSim/host.py:175](difuzz-rtl/Fuzzer/RTLSim/host.py#L175) | `self.adapter.probe_tohost(tohost_addr)` | 探测 tohost 地址 |

#### 7.6 停止模拟并保存签名

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:177](difuzz-rtl/Fuzzer/RTLSim/host.py#L177) | `yield self.adapter.stop()` | 停止适配器 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:177](difuzz-rtl/Fuzzer/RTLSim/host.py#L177)
> - **调用的方法**: `self.adapter.stop()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:120](difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L120)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/RTLSim/host.py:197](difuzz-rtl/Fuzzer/RTLSim/host.py#L197) | `self.save_signature(memory, sig_start, sig_end, data_addrs, self.rtl_sig_file)` | 保存签名 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:197](difuzz-rtl/Fuzzer/RTLSim/host.py#L197)
> - **调用的方法**: `self.save_signature()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/RTLSim/host.py:93](difuzz-rtl/Fuzzer/RTLSim/host.py#L93)

---

### Step 8: 结果比较 checker.check()

**调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:85](difuzz-rtl/Fuzzer/Fuzzer.py#L85)
<pre>
match = checker.check(symbols)
</pre>

**函数定义位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:114](difuzz-rtl/Fuzzer/src/signature_checker.py#L114)

#### 8.1 读取符号位置

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/signature_checker.py:116](difuzz-rtl/Fuzzer/src/signature_checker.py#L116) | `(xreg_idxes, freg_idxes, csr_idxes, data_symbols, data_idx_start) = self.read_symbols(symbols)` | 读取符号索引 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:116](difuzz-rtl/Fuzzer/src/signature_checker.py#L116)
> - **调用的方法**: `self.read_symbols()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:19](difuzz-rtl/Fuzzer/src/signature_checker.py#L19)

#### 8.2 读取签名文件

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/signature_checker.py:119](difuzz-rtl/Fuzzer/src/signature_checker.py#L119) | `(isa_xreg_vals, isa_freg_vals, isa_csr_vals, isa_data_vals) = self.read_sig(self.isa_sigfile, ...)` | 读取 ISA 签名 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:119](difuzz-rtl/Fuzzer/src/signature_checker.py#L119)
> - **调用的方法**: `self.read_sig()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/signature_checker.py:41](difuzz-rtl/Fuzzer/src/signature_checker.py#L41)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/signature_checker.py:123](difuzz-rtl/Fuzzer/src/signature_checker.py#L123) | `(rtl_xreg_vals, rtl_freg_vals, rtl_csr_vals, rtl_data_vals) = self.read_sig(self.rtl_sigfile, ...)` | 读取 RTL 签名 |

#### 8.3 比较寄存器

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/signature_checker.py:132](difuzz-rtl/Fuzzer/src/signature_checker.py#L132) | `for (i, val) in enumerate(zip(isa_xreg_vals, rtl_xreg_vals)):` | 遍历通用寄存器 |
| [difuzz-rtl/Fuzzer/src/signature_checker.py:133](difuzz-rtl/Fuzzer/src/signature_checker.py#L133) | `match = (val[0] == val[1])` | 比较 ISA 和 RTL 值 |
| [difuzz-rtl/Fuzzer/src/signature_checker.py:138](difuzz-rtl/Fuzzer/src/signature_checker.py#L138) | `for (i, val) in enumerate(zip(isa_freg_vals, rtl_freg_vals)):` | 遍历浮点寄存器 |
| [difuzz-rtl/Fuzzer/src/signature_checker.py:144](difuzz-rtl/Fuzzer/src/signature_checker.py#L144) | `for csr_name in csr_names:` | 遍历 CSR 寄存器 |

#### 8.4 比较内存数据

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/signature_checker.py:153](difuzz-rtl/Fuzzer/src/signature_checker.py#L153) | `for i in range(6):` | 遍历 6 个数据段 |
| [difuzz-rtl/Fuzzer/src/signature_checker.py:158](difuzz-rtl/Fuzzer/src/signature_checker.py#L158) | `if isa_data != rtl_data:` | 比较数据是否一致 |
| [difuzz-rtl/Fuzzer/src/signature_checker.py:170](difuzz-rtl/Fuzzer/src/signature_checker.py#L170) | `return (xreg_match & freg_match & csr_match & data_match)` | 返回比较结果 |

---

### Step 9: 覆盖率引导

#### 9.1 检查覆盖率增长

**文件**: `Fuzzer.py`

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/Fuzzer.py:112](difuzz-rtl/Fuzzer/Fuzzer.py#L112) | `if coverage > last_coverage:` | 检查覆盖率是否增长 |

#### 9.2 保存覆盖日志

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/Fuzzer.py:118](difuzz-rtl/Fuzzer/Fuzzer.py#L118) | `save_file(cov_log, 'a', ...)` | 保存覆盖率日志 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:118](difuzz-rtl/Fuzzer/Fuzzer.py#L118)
> - **调用的函数**: `save_file()`
> - **函数定义位置**: [difuzz-rtl/Fuzzer/src/utils.py:76](difuzz-rtl/Fuzzer/src/utils.py#L76)

#### 9.3 添加到语料库

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/Fuzzer.py:121](difuzz-rtl/Fuzzer/Fuzzer.py#L121) | `sim_input.save(out + '/corpus/id_{}.si'.format(cNum))` | 保存测试用例 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:121](difuzz-rtl/Fuzzer/Fuzzer.py#L121)
> - **调用的方法**: `sim_input.save()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:38](difuzz-rtl/Fuzzer/src/mutator.py#L38)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/Fuzzer.py:124](difuzz-rtl/Fuzzer/Fuzzer.py#L124) | `mutator.add_corpus(sim_input)` | 添加到变异器语料库 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:124](difuzz-rtl/Fuzzer/Fuzzer.py#L124)
> - **调用的方法**: `mutator.add_corpus()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:450](difuzz-rtl/Fuzzer/src/mutator.py#L450)

#### 9.4 更新变异阶段

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/Fuzzer.py:127](difuzz-rtl/Fuzzer/Fuzzer.py#L127) | `mutator.update_phase(it)` | 更新变异阶段 |

> **跨文件调用说明**:
> - **调用位置**: [difuzz-rtl/Fuzzer/Fuzzer.py:127](difuzz-rtl/Fuzzer/Fuzzer.py#L127)
> - **调用的方法**: `mutator.update_phase()`
> - **方法定义位置**: [difuzz-rtl/Fuzzer/src/mutator.py:438](difuzz-rtl/Fuzzer/src/mutator.py#L438)

##### 9.4.1 update_phase() 实现

**文件**: [difuzz-rtl/Fuzzer/src/mutator.py:438](difuzz-rtl/Fuzzer/src/mutator.py#L438)

| 行号 | 代码 | 说明 |
|------|------|------|
| [difuzz-rtl/Fuzzer/src/mutator.py:439](difuzz-rtl/Fuzzer/src/mutator.py#L439) | `if it < self.corpus_size / 10 or self.no_guide:` | 判断是否在初始化阶段 |
| [difuzz-rtl/Fuzzer/src/mutator.py:440](difuzz-rtl/Fuzzer/src/mutator.py#L440) | `self.phase = GENERATION` | 设置为生成阶段 |
| [difuzz-rtl/Fuzzer/src/mutator.py:443](difuzz-rtl/Fuzzer/src/mutator.py#L443) | `if rand < 0.1:` | 10% 概率生成 |
| [difuzz-rtl/Fuzzer/src/mutator.py:444](difuzz-rtl/Fuzzer/src/mutator.py#L444) | `self.phase = GENERATION` | |
| [difuzz-rtl/Fuzzer/src/mutator.py:445](difuzz-rtl/Fuzzer/src/mutator.py#L445) | `elif rand < 0.55:` | 45% 概率变异 |
| [difuzz-rtl/Fuzzer/src/mutator.py:446](difuzz-rtl/Fuzzer/src/mutator.py#L446) | `self.phase = MUTATION` | |
| [difuzz-rtl/Fuzzer/src/mutator.py:448](difuzz-rtl/Fuzzer/src/mutator.py#L448) | `self.phase = MERGE` | 45% 概率合并 |

---

## 3. 完整跨文件调用关系图

<pre>
DifuzzRTL.py (入口)
    │
    ├──► <a href="difuzz-rtl/Fuzzer/Fuzzer.py#L12">difuzz-rtl/Fuzzer/Fuzzer.py:12</a> (Run 协程)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/utils.py#L92">difuzz-rtl/Fuzzer/src/utils.py:92</a> (setup)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L93">difuzz-rtl/Fuzzer/src/mutator.py:93</a> (rvMutator)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/preprocessor.py#L10">difuzz-rtl/Fuzzer/src/preprocessor.py:10</a> (rvPreProcessor)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/ISASim/host.py#L10">difuzz-rtl/Fuzzer/ISASim/host.py:10</a> (rvISAhost)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L24">difuzz-rtl/Fuzzer/RTLSim/host.py:24</a> (rvRTLhost)
    │       │       │       └──► <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L22">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:22</a> (tileAdapter)
    │       │       │               └──► tilelink/adapter.py (tlAdapter)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L5">difuzz-rtl/Fuzzer/src/signature_checker.py:5</a> (sigChecker)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L356">difuzz-rtl/Fuzzer/src/mutator.py:356</a> (get)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/inst_generator.py#L158">difuzz-rtl/Fuzzer/src/inst_generator.py:158</a> (get_word)
    │       │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/word.py#L18">difuzz-rtl/Fuzzer/src/word.py:18</a> (Word)
    │       │       │       └──► <a href="difuzz-rtl/Fuzzer/src/word.py#L95-L236">difuzz-rtl/Fuzzer/src/word.py:95-236</a> (word_* 函数)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/src/inst_generator.py#L192">difuzz-rtl/Fuzzer/src/inst_generator.py:192</a> (populate_word)
    │       │               └──► <a href="difuzz-rtl/Fuzzer/src/word.py#L40">difuzz-rtl/Fuzzer/src/word.py:40</a> (populate)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/preprocessor.py#L57">difuzz-rtl/Fuzzer/src/preprocessor.py:57</a> (process)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L68">difuzz-rtl/Fuzzer/src/mutator.py:68</a> (get_prefix)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L76">difuzz-rtl/Fuzzer/src/mutator.py:76</a> (get_insts)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L38">difuzz-rtl/Fuzzer/src/mutator.py:38</a> (save)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/preprocessor.py#L26">difuzz-rtl/Fuzzer/src/preprocessor.py:26</a> (get_symbols)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/ISASim/host.py#L5">difuzz-rtl/Fuzzer/ISASim/host.py:5</a> (isaInput)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L16">difuzz-rtl/Fuzzer/RTLSim/host.py:16</a> (rtlInput)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/utils.py#L52">difuzz-rtl/Fuzzer/src/utils.py:52</a> (run_isa_test)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/ISASim/host.py#L22">difuzz-rtl/Fuzzer/ISASim/host.py:22</a> (run_test)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L111">difuzz-rtl/Fuzzer/RTLSim/host.py:111</a> (run_test)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L46">difuzz-rtl/Fuzzer/RTLSim/host.py:46</a> (set_bootrom)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L73">difuzz-rtl/Fuzzer/RTLSim/host.py:73</a> (clock_gen)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L81">difuzz-rtl/Fuzzer/RTLSim/host.py:81</a> (reset)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L111">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:111</a> (start)
    │       │       │       └──► tilelink/adapter.py (start)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L91">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:91</a> (interrupt_handler)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L105">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:105</a> (probe_tohost)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py#L120">difuzz-rtl/Fuzzer/RTLSim/src/adapters/tile_adapter.py:120</a> (stop)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/RTLSim/host.py#L93">difuzz-rtl/Fuzzer/RTLSim/host.py:93</a> (save_signature)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L114">difuzz-rtl/Fuzzer/src/signature_checker.py:114</a> (check)
    │       │       ├──► <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L19">difuzz-rtl/Fuzzer/src/signature_checker.py:19</a> (read_symbols)
    │       │       └──► <a href="difuzz-rtl/Fuzzer/src/signature_checker.py#L41">difuzz-rtl/Fuzzer/src/signature_checker.py:41</a> (read_sig)
    │       │
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/utils.py#L76">difuzz-rtl/Fuzzer/src/utils.py:76</a> (save_file)
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L38">difuzz-rtl/Fuzzer/src/mutator.py:38</a> (save)
    │       ├──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L450">difuzz-rtl/Fuzzer/src/mutator.py:450</a> (add_corpus)
    │       └──► <a href="difuzz-rtl/Fuzzer/src/mutator.py#L438">difuzz-rtl/Fuzzer/src/mutator.py:438</a> (update_phase)
    │
    └──► <a href="difuzz-rtl/Fuzzer/Minimizer.py#L14">difuzz-rtl/Fuzzer/Minimizer.py:14</a> (Minimize) [可选]
</pre>

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
