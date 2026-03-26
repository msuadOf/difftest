# DifuzzRTL - CPU 差分模糊测试

## Rules
- 所有的文字都强制使用utf-8中文
- 索引代码使用lsp plugins，如果有无法使用lsp的语言需要有提示
- 代码描述需要清晰明了：
  - 代码位置使用lsp plugins去索引，如果有无法使用lsp的语言需要有提示
  - 代码位置描述格式<workspace相对路径>:<行号>，markdown中实际链接格式`path/to/file#L196-L206`，即`[path/to/file:196-206](path/to/file#L196-L206)`
  - 描述调用关系需要有`调用位置`、`跳转的函数位置`
  - 描述完代码位置需要再次检查正确

## 一、代码结构(测试运行相关跳过本部分)

### 项目架构
```
difuzz-rtl/
├── firrtl/           # FIRRTL 编译器（插入寄存器覆盖率）
│   ├── src/          # Scala 源码
│   ├── utils/bin/    # firrtl 编译器可执行文件
│   └── regress/      # 测试用 FIRRTL 文件
├── Fuzzer/           # 主模糊测试框架
│   ├── src/          # 核心组件
│   │   ├── inst_generator.py  # RISC-V 指令生成器
│   │   ├── mutator.py         # 指令变异器
│   │   ├── preprocessor.py    # 测试用例预处理
│   │   ├── multicore_manager.py  # 多核管理
│   │   └── riscv_definitions.py  # RISC-V 指令定义
│   ├── RTLSim/       # RTL 仿真接口
│   │   ├── host.py   # Verilator 仿真主机
│   │   └── src/      # TileLink 适配器
│   ├── ISASim/       # ISA 仿真器（Spike）
│   ├── DifuzzRTL.py  # 主入口
│   ├── Fuzzer.py     # 核心模糊测试逻辑
│   └── Minimizer.py  # 测试用例最小化
└── Benchmarks/       # 测试基准
    ├── Firrtl/       # FIRRTL 源文件
    └── Verilog/      # 已插桩的 Verilog
        ├── RocketTile_state.v
        ├── SmallBoomTile_v1.2_state.v
        └── SmallBoomTile_v1.3_state.v
```

### 核心模块

#### 1. 指令生成 (`inst_generator.py`)
- **功能**: 生成语义正确的 RISC-V 指令序列
- **支持**: RV32/64 I/M/A/F/D/Q 扩展
- **特性**: 保证指令可编译且能向前执行

#### 2. 指令变异 (`mutator.py`)
- **功能**: 基于覆盖率引导的指令变异
- **策略**: 生成、变异、合并
- **模板**: p-m (Machine), p-s (Supervisor), p-u (User), v-u (Virtual User)

#### 3. 预处理 (`preprocessor.py`)
- **功能**: 将指令序列转换为可执行测试
- **输出**: ELF 文件、HEX 文件、符号表

#### 4. RTL 仿真 (`RTLSim/`)
- **接口**: Cocotb + Verilator
- **功能**: 运行 RTL 设计，采集覆盖率

#### 5. ISA 仿真 (`ISASim/`)
- **工具**: Spike (RISC-V ISA Simulator)
- **功能**: 作为参考模型验证 RTL

### 模糊测试流程
```
指令生成 → 变异 → 预处理 → 双仿真 → 差异检测
   ↓         ↓       ↓         ↓         ↓
RISC-V    覆盖率   ELF/HEX   RTL+ISA   Mismatch?
指令      引导     生成      并行      → 报告Bug
```

**详细步骤**:
1. **指令生成**: 生成符合 RISC-V 规范的指令序列
2. **变异**: 基于寄存器覆盖率选择和变异测试用例
3. **预处理**: 编译成 ELF，提取符号，生成内存初始化数据
4. **双仿真**:
   - RTL 仿真 (Verilator + Cocotb)
   - ISA 仿真 (Spike)
5. **差异检测**: 比较 RTL 和 ISA 的架构状态（寄存器、内存）

### 关键文件
- `Fuzzer/DifuzzRTL.py`: cocotb 入口文件，环境解析，目录创建
- `Fuzzer/Fuzzer.py`: Run 协程定义 (行12)，核心测试循环，差异检测
- `Fuzzer/src/mutator.py`: 测试用例生成、变异、语料库管理
- `Fuzzer/src/inst_generator.py`: RISC-V 指令生成逻辑
- `Fuzzer/RTLSim/host.py`: RTL 仿真接口，覆盖率采集
- `firrtl/src/main/scala/firrtl/`: FIRRTL 转换和插桩

### 代码约定
- **Python**: 使用 cocotb 协程 (`@coroutine`) 进行异步 RTL 仿真
- **Scala**: FIRRTL 转换使用函数式风格，不可变数据结构
- **测试输入格式**: `prefix + main_instructions + suffix + data`
- **命名**: `sim_input` = 测试输入，`mismatch` = 差异，`corpus` = 语料库

---

## 二、测试运行(阅读代码相关跳过本部分)
### 环境设置
```bash
cd difuzz-rtl
. ./setup.sh  # 安装依赖（elf2hex, spike）
source env.sh  # 设置环境变量（SPIKE, PYTHONPATH）
```

### 依赖版本
- verilator v4.106
- cocotb 1.5.2
- sbt (Scala Build Tool)
- riscv-gnu-toolchain 2021.04.23

### FIRRTL 插桩
```bash
cd firrtl
sbt compile; sbt assembly
./utils/bin/firrtl -td regress -i regress/<target>.fir \
  -fct coverage.regCoverage -X verilog -o <output>.v
```

**参数**:
- `-i`: 输入 FIRRTL 文件
- `-o`: 输出 Verilog 文件
- `-fct coverage.regCoverage`: 插入寄存器覆盖率

### 运行模糊测试
```bash
cd Fuzzer
make SIM_BUILD=<build_dir> VFILE=<target> TOPLEVEL=<module> \
     NUM_ITER=<iterations> OUT=<output_dir>
```

### 测试模式
#### 1. 单次测试
```bash
make VFILE=RocketTile_state TOPLEVEL=RocketTile NUM_ITER=1000 OUT=test_out
```

#### 2. 多核并行
```bash
make VFILE=RocketTile_state TOPLEVEL=RocketTile NUM_ITER=10000 \
     OUT=multi_out MULTICORE=4
```

#### 3. 覆盖率记录
```bash
make VFILE=RocketTile_state TOPLEVEL=RocketTile NUM_ITER=5000 \
     OUT=cov_out RECORD=1
```

#### 4. 调试模式
```bash
make VFILE=RocketTile_state TOPLEVEL=RocketTile NUM_ITER=100 \
     OUT=debug_out DEBUG=1
```

#### 5. 重放测试用例
```bash
make VFILE=RocketTile_state TOPLEVEL=RocketTile \
     IN_FILE=output/mismatch/sim_input/case_001.txt
```

### 常见问题

1. **Verilator 版本不匹配**
   - 错误: 编译失败或仿真异常
   - 解决: 确保使用 v4.106

2. **Cocotb 导入错误**
   - 错误: `ModuleNotFoundError: No module named 'cocotb'`
   - 解决: `pip install cocotb==1.5.2`

3. **Spike 找不到**
   - 错误: `spike: command not found`
   - 解决: `source env.sh` 或检查 `SPIKE` 环境变量

4. **PYTHONPATH 错误**
   - 错误: `ModuleNotFoundError: No module named 'src'`
   - 解决: `source env.sh`

5. **覆盖率不增长**
   - 原因: 语料库未更新或测试用例质量低
   - 解决: 检查 `corpus/` 目录，增加迭代次数

6. **多核测试失败**
   - 错误: 子进程异常退出
   - 解决: 检查 `mismatch/` 中的失败用例，减少并行数

### 调试技巧

- **详细日志**: `DEBUG=1` 打印每条指令的执行
- **覆盖率追踪**: `RECORD=1` 生成覆盖率曲线
- **失败用例分析**: 查看 `mismatch/asm/` 中的反汇编
- **单步重放**: 使用 `IN_FILE` 重放特定用例
- **最小化**: `MINIMIZE=1` 简化失败用例
- **中断测试**: 设置 `prob_intr` 参数测试中断处理
