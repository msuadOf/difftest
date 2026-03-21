# 二进制文件直接运行 Difftest 计划

## 目标描述

修改 DifuzzRTL 项目，使其支持直接加载 `progs/` 目录下已编译好的 `.bin`/`.elf` 二进制文件，让 DUT（RTL 仿真器）和 Spike（RISC-V 参考模拟器）都直接运行该二进制文件，最终比对两者执行后输出的签名，判断是否存在行为差异。整个流程**不使用** DifuzzRTL 的 Template 相关逻辑（模糊测试指令生成、汇编模板、随机变异等）。

---

## 验收标准

遵循 TDD 哲学，每个标准包含正向测试（预期通过）和负向测试（预期失败）以实现确定性验证。

- **AC-1**：能够从 `progs/` 目录读取 `.elf` 或 `.bin` 文件，并直接供 Spike 和 RTL 仿真器使用
  - 正向测试（预期通过）：
    - 给定 `progs/rv32d_addi_x0_x0_0x0_Retire_Success.elf`，程序能读取该文件路径并传递给 Spike 运行，Spike 输出签名文件
    - 给定 `.elf` 文件，程序能从其中提取符号表（`reg_x0_output`、`begin_signature` 等），用于后续签名比对
  - 负向测试（预期失败）：
    - 给定一个不存在的路径，程序报错并退出，而不是静默继续
    - 给定一个非 RISC-V ELF 文件，符号提取失败并有明确错误提示

- **AC-2**：Spike 能直接运行指定的 `.elf` 文件并输出签名
  - 正向测试（预期通过）：
    - Spike 以 `+signature=<sigfile>` 参数运行 ELF 文件后，签名文件被创建且非空
    - 签名文件格式与 `signature_checker.py` 的解析格式一致（每行两个十六进制值）
  - 负向测试（预期失败）：
    - 若 Spike 可执行文件路径不存在，程序报错而非挂起
    - 若 ELF 文件缺少必要符号（如 `begin_signature`），签名比对时给出明确提示

- **AC-3**：RTL 仿真器（cocotb）能直接加载来自 `.elf` 的 hex 内存数据并运行仿真
  - 正向测试（预期通过）：
    - 从 ELF 文件生成的 hex 内存数据能被 `RTLSim/host.py` 正确加载到内存字典
    - RTL 仿真运行到 `tohost` 信号置位后正常停止，并输出 RTL 签名文件
  - 负向测试（预期失败）：
    - 若 hex 数据为空，RTL 仿真报错而非运行空程序
    - 若内存地址超出合法范围，仿真报错 `ILL_MEM`

- **AC-4**：签名比对逻辑能正确比较 Spike 和 RTL 的执行结果
  - 正向测试（预期通过）：
    - 对行为一致的程序（DUT 与 Spike 输出相同），比对结果返回"无差异"
    - 对已知存在 x 寄存器不匹配的测试程序，比对结果输出具体寄存器名和差异值
  - 负向测试（预期失败）：
    - 若 ISA 签名文件或 RTL 签名文件不存在，比对程序报错而非返回误判的"通过"

- **AC-5**：新增入口脚本（`run_difftest.py`）能够端到端运行单个 `.elf` 文件的 difftest
  - 正向测试（预期通过）：
    - 运行 `python run_difftest.py --elf progs/xxx.elf` 后，在终端输出"PASS"或"MISMATCH"结论
    - 对 `progs/` 中多个文件批量运行时，每个文件各自输出结论，互不干扰
  - 负向测试（预期失败）：
    - 不带 `--elf` 参数运行时，脚本打印使用说明并退出，不崩溃

---

## 路径边界

### 上界（最大可接受范围）
实现包含：新入口脚本 `run_difftest.py`、ELF 符号提取工具函数、从 ELF 生成 hex 内存的加载器、对 `ISASim/host.py` 和 `RTLSim/host.py` 的最小修改（支持直接传入 ELF/hex），以及对 `signature_checker.py` 的复用（无需修改）。支持批量运行 `progs/` 目录下所有 `.elf` 文件并汇总结果。

### 下界（最小可接受范围）
实现包含：新入口脚本 `run_difftest.py`，能对 `progs/` 中单个 `.elf` 文件完成端到端的 Spike 运行 → RTL 运行 → 签名比对流程，并输出 PASS/MISMATCH 结论。

### 允许的选择
- **可以使用**：
  - `ISASim/host.py`（复用或最小修改）
  - `RTLSim/host.py`（复用或最小修改）
  - `src/signature_checker.py`（直接复用，无需修改）
  - `progs/` 中已有的 `.elf`、`.hex`、`.bin` 文件
  - Python 标准库 + `pyelftools` 或 `riscv64-unknown-elf-nm` 提取 ELF 符号
  - cocotb 仿真框架（已有依赖）
- **不可以使用**：
  - `src/inst_generator.py`（随机指令生成）
  - `src/mutator.py`（模糊测试变异与语料库管理）
  - `Template/` 目录下任何文件（汇编模板）
  - `src/preprocessor.py` 的模板编译路径（可借用其 ELF 符号提取函数）

> **说明**：本设计高度确定性——必须使用 ELF 文件作为输入，禁止模板生成，路径边界较窄。

---

## 可行性提示与建议

> **注意**：本节仅供参考理解，为概念性建议，非强制要求。

### 概念性思路

```
输入：progs/xxx.elf
     │
     ├─→ [ELF 解析器]
     │       ├─ 提取符号表 (nm 或 pyelftools)
     │       │     → reg_x0_output, begin_signature, ...
     │       └─ 生成 hex 内存字典
     │             → {addr: value, ...} (64-bit 对齐)
     │
     ├─→ [Spike 运行]
     │       spike <args> +signature=isa_sig.txt xxx.elf
     │       → 生成 isa_sig.txt
     │
     ├─→ [RTL 仿真]
     │       RTLSim/host.py.run_test(hex_dict, symbols)
     │       → 生成 rtl_sig.txt
     │
     └─→ [签名比对]
             sigChecker.check(symbols)
             → PASS / MISMATCH (含寄存器差异详情)
```

**关键实现点：**

1. **ELF → hex 内存转换**：读取 ELF 的 `.text` / `.data` / `.bss` 段，按 64-bit 对齐写入内存字典，起始地址为 `0x80000000`（DRAM_BASE）。

2. **符号提取**：可复用 `preprocessor.py` 中的 `get_symbols()` 方法（调用 `riscv64-unknown-elf-nm`），或使用 `pyelftools` 直接解析。

3. **Spike 调用**：`ISASim/host.py` 的 `run_test()` 已支持直接传入 ELF 路径，只需确保不依赖 template 预处理步骤即可复用。

4. **RTL hex 加载**：若 `progs/` 中已有对应 `.hex` 文件，可直接复用；若仅有 `.elf`，需用 `riscv64-unknown-elf-objcopy -O ihex` 或手动解析 ELF 段生成 hex。

5. **入口脚本**：新建 `run_difftest.py`，解析命令行参数（`--elf`、`--progs-dir`），调用上述流程，不依赖 cocotb Makefile（或最小依赖）。

### 相关参考路径
- `difuzz-rtl/Fuzzer/ISASim/host.py` — Spike 运行封装
- `difuzz-rtl/Fuzzer/RTLSim/host.py` — RTL cocotb 仿真封装
- `difuzz-rtl/Fuzzer/src/signature_checker.py` — 签名比对逻辑
- `difuzz-rtl/Fuzzer/src/preprocessor.py` — 符号提取函数（`get_symbols`）可复用
- `progs/` — 已有 .elf/.hex/.bin 测试程序

---

## 依赖关系与里程碑

### 里程碑

1. **ELF 加载与符号提取**：实现从 `.elf` 文件提取符号表和内存数据的工具函数
   - 阶段 A：封装 `get_symbols(elf_path)` — 返回符号名→地址字典
   - 阶段 B：封装 `elf_to_hex(elf_path)` — 返回地址→值的内存字典（供 RTL 仿真使用）

2. **Spike 运行**：验证 `ISASim/host.py` 能直接接受 `.elf` 路径运行并生成签名
   - 依赖里程碑 1 完成（需符号信息）
   - 阶段 A：最小化修改 `ISASim/host.py`，去除对 preprocessor 的依赖
   - 阶段 B：验证签名文件格式正确

3. **RTL 仿真**：验证 `RTLSim/host.py` 能接受来自 ELF 的 hex 内存字典运行仿真
   - 依赖里程碑 1 完成（需 hex 内存数据）
   - 阶段 A：最小化修改 `RTLSim/host.py`，接受内存字典作为输入
   - 阶段 B：确认 `tohost` 信号检测和签名保存逻辑正常工作

4. **签名比对集成**：将上述步骤串联，调用 `signature_checker.py` 完成比对
   - 依赖里程碑 2、3 完成
   - `signature_checker.py` 无需修改，直接复用

5. **入口脚本**：新建 `run_difftest.py`，端到端运行并输出结论
   - 依赖里程碑 1–4 完成
   - 阶段 A：单文件运行模式（`--elf <path>`）
   - 阶段 B：批量运行模式（`--progs-dir <dir>`）

---

## 实现注意事项

### 代码风格要求
- 实现代码和注释中**不得**包含计划专属术语，如 "AC-"、"里程碑"、"阶段"、"步骤" 或类似进度标记词汇
- 这些术语仅用于本计划文档，不应出现在最终代码库中
- 代码中请使用描述性的、符合领域语义的命名

---

## 原始草稿（保留参考）

> 我有一个二进制文件（.bin 文件，存放在 progs/ 目录下），里面有一些指令流。
>
> 我想利用这个仓库的部分代码进行 difftest：
> - 让 DUT（被测设备）和 Spike（RISC-V 参考模拟器）都直接运行我的这个二进制文件
> - 最后比对两者执行之后的签名（signature）
>
> 约束条件：
> - **不允许**使用 DifuzzRTL 的 template 相关逻辑
> - 只需要使用该项目的 difftest 逻辑部分
>
> 目标：修改这个项目，使其支持直接加载并运行 .bin 文件进行 difftest，而不依赖 DifuzzRTL 的模糊测试 template 生成机制。
