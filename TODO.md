# Difftest 项目开发任务清单

## 项目目标

将 `progs/` 目录下的 `.bin` 文件作为输入，利用 difuzz-rtl 中的 difftest 机制进行差分测试，输出比对结果。

---

## 一、环境配置任务

### 1.1 Docker 容器配置

**任务描述**：修改容器启动方式，将本地项目目录映射到容器内部。

**具体要求**：
- 使用 `diffuzzrtl` 镜像创建容器
- 通过 `-v` 参数将本地项目目录挂载到容器中
- 确保容器内可以访问和执行本地修改的代码

**示例命令**：
```bash
# 原始方式（不推荐）
docker run -it diffuzzrtl /bin/bash

# 改进方式（推荐）
docker run -it \
  -v /home/baiyifan/workplace-local/difftest:/home/host/difftest \
  -w /home/host/difftest \
  diffuzzrtl /bin/bash
```

**验证方法**：
```bash
# 在容器内验证挂载成功
ls /home/host/difftest/progs/*.bin | head -5
```

---

### 1.2 依赖工具安装

**任务描述**：在容器内配置必要的编译工具链。

**具体要求**：
- 安装 `elf2hex` 工具
- 编译 `riscv-isa-sim` (Spike 模拟器)
- 配置环境变量

**示例操作**：
```bash
# 进入 difuzz-rtl 目录
cd /home/host/difftest/difuzz-rtl

# 执行安装脚本
./setup.sh

# 配置环境变量（可添加到 ~/.bashrc）
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/RTLSim/src
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/src
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer
export SPIKE=/home/host/difftest/difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/build/spike
```

---

## 二、代码开发任务

### 2.1 创建独立的 difftest 运行脚本

**任务描述**：新建一个独立的脚本，能够直接读取 `.bin` 文件并执行 difftest。

**具体要求**：
- 新建 `scripts/` 目录存放工具脚本
- 支持从 `.bin` 文件读取指令流
- 复用 difuzz-rtl 中的 `preprocessor`、`isaHost`、`rtlHost`、`sigChecker` 组件

**文件结构示例**：
```
difftest/
├── scripts/
│   ├── run_difftest.py      # 主运行脚本
│   ├── bin_reader.py        # bin 文件解析器
│   └── result_formatter.py  # 结果格式化输出
├── progs/                   # 测试用例目录
│   ├── *.bin
│   ├── *.asm
│   └── *.hex
└── difuzz-rtl/              # 原有代码库
```

**示例代码框架** (`scripts/run_difftest.py`)：
```python
#!/usr/bin/env python3
import os
import sys
import argparse

# 添加 difuzz-rtl 路径
sys.path.insert(0, '/home/host/difftest/difuzz-rtl/Fuzzer')

from src.preprocessor import rvPreProcessor
from src.signature_checker import sigChecker
from ISASim.host import rvISAhost, isaInput
from RTLSim.host import rvRTLhost, rtlInput

def load_bin_file(bin_path):
    """加载 bin 文件，返回指令流"""
    # 实现细节：解析 .bin 文件或关联的 .asm/.hex 文件
    pass

def run_difftest_single(bin_file, output_dir):
    """对单个 bin 文件执行 difftest"""
    # 1. 加载指令流
    # 2. 预处理：生成 ELF 和 HEX
    # 3. 运行 ISA 仿真
    # 4. 运行 RTL 仿真
    # 5. 比对签名
    # 6. 输出结果
    pass

def main():
    parser = argparse.ArgumentParser(description='Difftest Runner')
    parser.add_argument('--bin', required=True, help='Path to bin file or directory')
    parser.add_argument('--out', default='output', help='Output directory')
    args = parser.parse_args()

    # 执行测试逻辑
    pass

if __name__ == '__main__':
    main()
```

---

### 2.2 实现 bin 文件解析器

**任务描述**：编写模块解析 `progs/` 目录下的 `.bin` 文件。

**具体要求**：
- 读取二进制指令流
- 支持关联的 `.asm`、`.hex`、`.elf` 文件（如果存在）
- 转换为 difuzz-rtl 可识别的 `simInput` 格式

**输入文件格式示例**：
```
progs/
├── rv32d_addi_x0_x0_0x0_Retire_Success.bin   # 原始二进制
├── rv32d_addi_x0_x0_0x0_Retire_Success.asm   # 汇编代码（可选）
├── rv32d_addi_x0_x0_0x0_Retire_Success.hex   # HEX 格式（可选）
└── rv32d_addi_x0_x0_0x0_Retire_Success.elf   # ELF 格式（可选）
```

**示例代码** (`scripts/bin_reader.py`)：
```python
import os

class BinReader:
    def __init__(self, bin_path):
        self.bin_path = bin_path
        self.base_path = os.path.splitext(bin_path)[0]

    def has_elf(self):
        """检查是否存在对应的 ELF 文件"""
        return os.path.exists(self.base_path + '.elf')

    def has_hex(self):
        """检查是否存在对应的 HEX 文件"""
        return os.path.exists(self.base_path + '.hex')

    def get_elf_path(self):
        """获取 ELF 文件路径"""
        return self.base_path + '.elf'

    def get_hex_path(self):
        """获取 HEX 文件路径"""
        return self.base_path + '.hex'

    def read_binary_instructions(self):
        """直接从 bin 文件读取指令流"""
        with open(self.bin_path, 'rb') as f:
            binary_data = f.read()

        # 将二进制数据转换为 32 位指令
        instructions = []
        for i in range(0, len(binary_data), 4):
            word = int.from_bytes(binary_data[i:i+4], 'little')
            instructions.append(word)
        return instructions

    def read_hex_file(self):
        """读取 HEX 格式文件"""
        hex_path = self.get_hex_path()
        if not os.path.exists(hex_path):
            raise FileNotFoundError(f"HEX file not found: {hex_path}")

        with open(hex_path, 'r') as f:
            lines = f.readlines()

        return [int(line.strip(), 16) for line in lines if line.strip()]
```

---

### 2.3 适配现有的 preprocessor 模块

**任务描述**：修改或封装 `rvPreProcessor` 类以支持直接使用已有的 ELF/HEX 文件。

**具体要求**：
- 如果已有 `.elf` 文件，跳过编译步骤
- 如果已有 `.hex` 文件，跳过 elf2hex 转换步骤
- 生成 `isaInput` 和 `rtlInput` 对象供后续使用

**示例代码**：
```python
class DiffTestPreProcessor:
    def __init__(self, bin_reader, template_path, output_base):
        self.bin_reader = bin_reader
        self.template_path = template_path
        self.output_base = output_base

    def process_existing_files(self):
        """处理已有的 ELF/HEX 文件"""
        if self.bin_reader.has_elf():
            elf_path = self.bin_reader.get_elf_path()
        else:
            # 需要编译生成 ELF
            elf_path = self._compile_from_binary()

        if self.bin_reader.has_hex():
            hex_path = self.bin_reader.get_hex_path()
        else:
            # 需要转换生成 HEX
            hex_path = self._convert_elf_to_hex(elf_path)

        # 提取符号表
        symbols = self._extract_symbols(elf_path)

        # 创建输入对象
        isa_input = isaInput(elf_path, intr_file=None)
        rtl_input = rtlInput(hex_path, intr_file=None, data=[], symbols=symbols, max_cycles=6000)

        return isa_input, rtl_input, symbols
```

---

### 2.4 实现签名比对逻辑

**任务描述**：封装 `sigChecker` 类，输出格式化的比对结果。

**具体要求**：
- 比对通用寄存器 (x0-x31)
- 比对浮点寄存器 (f0-f31)
- 比对 CSR 寄存器
- 比对内存数据区域
- 输出详细的差异报告

**示例输出格式**：
```
================== Difftest Result ==================
Test File: rv32d_addi_x0_x0_0x0_Retire_Success.bin
Status: PASS / MISMATCH

--- Register Comparison ---
(x00 | zero) [ISA] 0000000000000000 || [RTL] 0000000000000000 ✓
(x01 | ra  ) [ISA] 0000000000000000 || [RTL] 0000000000000000 ✓
...

--- CSR Comparison ---
(mstatus  ) [ISA] 0000000a00000000 || [RTL] 0000000a00000000 ✓
...

--- Memory Data Comparison ---
(_random_data0) ✓
...

================== Summary ==================
Total Checks: 128
Passed: 128
Failed: 0
Result: PASS
=====================================================
```

---

## 三、集成测试任务

### 3.1 批量测试脚本

**任务描述**：创建脚本批量运行 `progs/` 目录下所有测试用例。

**示例代码** (`scripts/batch_run.py`)：
```python
#!/usr/bin/env python3
import os
import glob
import json
from datetime import datetime

def batch_run(progs_dir, output_dir):
    """批量运行所有测试用例"""
    bin_files = glob.glob(os.path.join(progs_dir, '*.bin'))

    results = {
        'total': len(bin_files),
        'passed': 0,
        'failed': 0,
        'errors': 0,
        'details': []
    }

    for bin_file in sorted(bin_files):
        print(f"Testing: {os.path.basename(bin_file)}")

        try:
            result = run_difftest_single(bin_file, output_dir)
            if result['match']:
                results['passed'] += 1
            else:
                results['failed'] += 1
            results['details'].append(result)
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'file': bin_file,
                'status': 'error',
                'message': str(e)
            })

    # 保存结果摘要
    report_path = os.path.join(output_dir, f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    return results

if __name__ == '__main__':
    results = batch_run('/home/host/difftest/progs', '/home/host/difftest/output')
    print(f"\nTotal: {results['total']}, Passed: {results['passed']}, Failed: {results['failed']}, Errors: {results['errors']}")
```

---

### 3.2 Docker 运行封装

**任务描述**：创建 Docker 一键运行脚本。

**示例脚本** (`run_docker.sh`)：
```bash
#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="diffuzzrtl"

# 运行单个测试
run_single() {
    local bin_file=$1
    docker run --rm \
        -v "$PROJECT_DIR:/home/host/difftest" \
        -w /home/host/difftest \
        $IMAGE_NAME \
        python3 scripts/run_difftest.py --bin "$bin_file" --out output
}

# 批量运行
run_batch() {
    docker run --rm \
        -v "$PROJECT_DIR:/home/host/difftest" \
        -w /home/host/difftest \
        $IMAGE_NAME \
        python3 scripts/batch_run.py
}

case "$1" in
    single)
        run_single "$2"
        ;;
    batch)
        run_batch
        ;;
    *)
        echo "Usage: $0 {single|batch} [bin_file]"
        exit 1
        ;;
esac
```

**使用示例**：
```bash
# 运行单个测试
./run_docker.sh single progs/rv32d_addi_x0_x0_0x0_Retire_Success.bin

# 批量运行所有测试
./run_docker.sh batch
```

---

## 四、目录结构规划

完成后的项目目录结构：

```
difftest/
├── scripts/
│   ├── run_difftest.py       # 单文件 difftest 运行脚本
│   ├── batch_run.py          # 批量运行脚本
│   ├── bin_reader.py         # bin 文件解析器
│   └── result_formatter.py   # 结果格式化输出
├── progs/                    # 测试用例（已有）
│   └── *.bin, *.asm, *.hex, *.elf
├── output/                   # 输出目录
│   ├── mismatch/             # 不匹配的结果
│   ├── logs/                 # 日志文件
│   └── report_*.json         # 测试报告
├── difuzz-rtl/               # difuzz-rtl 代码库（已有）
├── run_docker.sh             # Docker 运行脚本
├── TODO.md                   # 本文档
└── README.md                 # 项目说明文档
```

---

## 五、执行顺序建议

| 优先级 | 任务 | 预计复杂度 |
|--------|------|------------|
| P0 | 1.1 Docker 容器配置 | 低 |
| P0 | 1.2 依赖工具安装 | 中 |
| P1 | 2.2 实现 bin 文件解析器 | 中 |
| P1 | 2.1 创建独立的 difftest 运行脚本 | 高 |
| P2 | 2.3 适配现有的 preprocessor 模块 | 中 |
| P2 | 2.4 实现签名比对逻辑 | 中 |
| P3 | 3.1 批量测试脚本 | 低 |
| P3 | 3.2 Docker 运行封装 | 低 |

---

## 六、注意事项

1. **文件格式兼容性**：`progs/` 目录下的文件名以 `rv32d_` 开头，但 difuzz-rtl 默认使用 RV64G 架构，需要注意架构兼容性问题。

2. **RTL 仿真依赖**：RTL 仿真需要 Verilog 编译环境（如 Verilator）和 cocotb，确保容器内已正确配置。

3. **符号表提取**：difftest 需要提取 `begin_signature`、`end_signature` 等符号地址，确保测试程序包含这些符号定义。

4. **内存数据区域**：原有 difuzz-rtl 使用 6 个随机数据区域 (`_random_data0` ~ `_random_data5`)，需要适配 `progs/` 中测试用例的实际内存布局。
