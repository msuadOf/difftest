# v-u 模板启动流程分析

## 一、模板总览

v-u（Virtual-User）模板是 Difuzz-RTL 中唯一启用 SV39 虚拟内存的模板。与 p-m/p-s/p-u 模板（物理地址直映射）不同，它通过缺页异常驱动按需分配，并在映射时注入随机 PTE 标志位，用于 fuzz TLB/MMU 路径。

涉及文件：
- [rv64-v-u.S](rv64-v-u.S)：汇编入口、trap 处理、寄存器 dump
- [include/v/vm.c](include/v/vm.c)：页表初始化、缺页处理、启动流程
- [include/v/riscv_test.h](include/v/riscv_test.h)：页表常量定义
- [include/fuzz_test.h](../include/fuzz_test.h)：INIT_XREGS/INIT_FREGS/DUMP_REGS 宏

## 二、完整执行流程

### 2.1 第一阶段：硬件复位 → handle_reset

```
bootrom (0x10000): auipc/jr → 0x80000000
```

进入 `_start` → `j handle_reset`（[rv64-v-u.S:31-32](rv64-v-u.S#L31-L32)）。

**handle_reset**（[rv64-v-u.S:51-65](rv64-v-u.S#L51-L65)）：

| 操作 | 说明 |
|------|------|
| `INIT_XREGS` | 从 `_random_data0` 加载随机值到 x1~x31 |
| `csrw mtvec, trap_mtvec` | 设置 M-mode trap 向量 |
| `la sp, STACK_TOP - ...` | 设置内核栈指针 |
| `csrw mscratch, sp` | 保存 sp，供后续 S-mode trap 使用 |
| `csrs mstatus, MSTATUS_FS` | 开启 FPU |
| `call init_freg` | 从 `_random_data1` 加载随机值到 f0~f31 |
| `la a0, userstart` | a0 = userstart 的**物理地址** |
| `j vm_boot` | 跳转到 C 函数 |

此时状态：**M-mode，物理地址，无虚拟内存**。

### 2.2 第二阶段：vm_boot

[vm.c:254-331](include/v/vm.c#L254-L331)，`vm_boot(uintptr_t test_addr)`，其中 `test_addr` = userstart 的物理地址。

#### 2.2.1 建页表（SV39）

页表定义（[riscv_test.h:61](include/v/riscv_test.h#L61)、[vm.c:79-97](include/v/vm.c#L79-L97)）：

```c
#define MAX_TEST_PAGES 127
#define PTES_PER_PT 512

pte_t pt[4][512] __attribute__((aligned(4096)));
// pt[0] = l1pt        (L1 根页表)
// pt[1] = user_l2pt   (L2 用户页表)
// pt[2] = kernel_l2pt (L2 内核页表)
// pt[3] = user_llpt   (L3 用户叶页表，初始全空)
```

建立的映射（[vm.c:266-277](include/v/vm.c#L266-L277)）：

```
SV39 虚拟地址: [8] [9] [9] [12]

L1 (l1pt):
  ├─ [0]     ──► user_l2pt         用户空间 VA 0x0 ~ 0x3F_FFFF_FFFF
  └─ [511]   ──► kernel_l2pt       内核空间 VA 0xFFFF_FFFF_80000000 ~

L2:
  ├─ user_l2pt[0]    ──► user_llpt   VA 0x0 ~ 0x3FFFFF 的叶页表
  └─ kernel_l2pt[511] ──► 2MB 大页直映射 DRAM_BASE
                            PTE = R|W|X|A|D|V

虚拟地址空间布局:
  0x0000_0000_0000 ┌─────────────────────┐
                    │  用户代码/数据       │  ← userstart
                    │  由 user_llpt 按需映射│  VA = PA - DRAM_BASE - 2MB
  0x0000_003F_FFFF ├─────────────────────┤
                    │  (未映射)            │
                    │  ...                 │
  0xFFFF_FFFF_8000 ├─────────────────────┤ = DRAM_BASE
                    │  内核空间            │
                    │  trap_entry/vm.c    │  VA = PA (大页直映射)
                    │  页表/数据结构       │
  0xFFFF_FFFF_FFFF └─────────────────────┘
```

#### 2.2.2 开虚拟内存 + 配置 trap

[vm.c:283-311](include/v/vm.c#L283-L311)：

```c
write_csr(satp, SV39 | l1pt);          // MMU 开始工作
write_csr(stvec, pa2kva(trap_entry));   // S-mode 向量 → trap_entry（汇编）
write_csr(sscratch, pa2kva(mscratch));  // 把 handle_reset 保存的 sp 转给 S-mode
write_csr(medeleg,                     // 委托以下异常到 S-mode
    (1 << CAUSE_USER_ECALL) |           //   8
    (1 << CAUSE_FETCH_PAGE_FAULT) |     //   12
    (1 << CAUSE_LOAD_PAGE_FAULT) |      //   13
    (1 << CAUSE_STORE_PAGE_FAULT));     //   15
write_csr(mstatus, MSTATUS_FS | MSTATUS_XS);
write_csr(mie, 0);                      // 清 mie（暂时关中断）
```

注意：**mideleg 未设置**，所有中断不委托，直接到 M-mode。

#### 2.2.3 初始化物理页空闲链表

[vm.c:313-322](include/v/vm.c#L313-L322)：

```c
freelist_nodes[i].addr = DRAM_BASE + (MAX_TEST_PAGES + random) * PGSIZE;
// 127 个物理页，用 LFSR 伪随机排列
```

这些物理页用于缺页时按需分配给 user_llpt。

#### 2.2.4 执行 _fuzz_prefix

[vm.c:324](include/v/vm.c#L324)：`_fuzz_prefix()` 作为 C 函数调用。

汇编布局（[rv64-v-u.S:43-49](rv64-v-u.S#L43-L49)）：

```asm
  .global _fuzz_prefix
  init_mie;              ← 在 label 之前！函数入口在这里
_fuzz_prefix:
    /* mutator 插入的 CSR 指令 */
_end_prefix:
    ret
```

调用顺序：**先执行 `init_mie` 宏，再执行 mutator 插入的 CSR 指令，最后 `ret`**。

`init_mie`（[fuzz_test.h:4-14](../include/fuzz_test.h#L4-L14)）做了：

```c
csrs mstatus, MPIE | SPIE | UPIE;     // 允许中断返回
csrwi mie, 0;
csrs mie, MEIP | SEIP | MTIP | MSIP;  // 重新开启中断使能！
```

**因此 prefix 执行完后 mie 被重新设上，中断是开启的。** 后续用户代码执行时中断可以触发。

#### 2.2.5 进入用户态

[vm.c:325-330](include/v/vm.c#L325-L330)：

```c
write_csr(mtvec, trap_mtvec);    // 更新 M-mode 向量

trapframe_t tf;
memset(&tf, 0, sizeof(tf));       // 全部清零
tf.epc = test_addr - DRAM_BASE;   // userstart 的虚拟地址
pop_tf(&tf);                      // 恢复寄存器 + sret
```

`pop_tf`（[rv64-v-u.S:94-129](rv64-v-u.S#L94-L129)）：
- 从 trapframe 恢复 sepc = userstart 虚拟地址
- 恢复 x1~x31（全部为 0，因为 memset 了）
- `sret`：trapframe 里 sstatus=0，SPP=0 → **降到 U-mode**，PC = userstart

### 2.3 第三阶段：_fuzz_main（U-mode，虚拟地址）

mutator 插入的核心指令在此执行。寄存器初值全部为 0（pop_tf 恢复的）。

#### 2.3.1 缺页路径

用户代码访问未映射页 → StorePageFault/LoadPageFault/FetchPageFault（已委托 S-mode）：

```
trap_entry (S-mode, 由 stvec 向量进入)
  ├─ csrrw sp, sscratch, sp     交换到内核栈
  ├─ STORE x1~x31              保存所有 GPR 到 trapframe
  ├─ STORE sstatus, sepc, sbadaddr, scause
  └─ j handle_trap

handle_trap (C, S-mode)          [vm.c:198-236]
  └─ handle_fault(addr, cause)   [vm.c:152-196]
       ├─ 已有映射缺 A/D 位？→ 补标志位，sfence.vma，返回
       └─ 新映射？
            ├─ 10% 概率：正常 PTE (V|U|R|W|X)
            ├─ 90% 概率：随机 PTE 标志位（可能缺 R/W/X/V 等）
            ├─ 复制初始数据到新页
            └─ sfence.vma

pop_tf (S-mode)
  ├─ 恢复 sepc, x1~x31
  └─ sret → 回 U-mode，重试出错的指令
```

**随机 PTE 注入是 v-u 模板的核心**——迫使 TLB/MMU 处理各种异常权限组合，这是 p-m 模板（直映射）完全覆盖不到的路径。

#### 2.3.2 正常退出路径

用户代码执行到 `ecall`（U-mode, cause=8, 已委托 S-mode）：

```
trap_entry (S-mode)
  └─ 保存 trapframe → j handle_trap

handle_trap (C, S-mode)
  ├─ cause != 缺页 → else 分支
  ├─ evict() 写回脏页
  └─ trap_stvec()          ← C 函数调用（不是向量跳转！）

trap_stvec (S-mode, 函数调用)  [rv64-v-u.S:73-80]
  ├─ clear_sie             关闭 S-mode 中断
  ├─ _fuzz_suffix          mutator 插入的指令（在 S-mode 下执行）
  └─ ecall                 S-mode ecall, cause=9
                            CAUSE_SUPERVISOR_ECALL 未委托 → M-mode

trap_mtvec (M-mode)           [rv64-v-u.S:83-91]
  ├─ clear_mie
  ├─ DUMP_REGS              保存架构状态到签名区
  └─ write_tohost            tohost=1, 仿真停止
```

**`handle_trap` 里的 `pop_tf(tf)` 永远不会执行到**——`trap_stvec()` 的 ecall 陷到 M-mode 后就不再返回。

#### 2.3.3 中断路径

中断信号到来时（mie 已由 `init_mie` 开启，mideleg 未设）：

```
中断 → M-mode trap_mtvec（不经过 S-mode）
  ├─ clear_mie
  ├─ DUMP_REGS
  └─ write_tohost → 仿真停止
```

中断直接终止测试，不会进入 S-mode trap_entry。这是设计意图——中断导致的状态不可预测，直接 dump 并结束。

## 三、fuzz 指令区域对比

| 区域 | 汇编位置 | 执行模式 | 执行时机 | mutator 插入内容 |
|------|---------|---------|---------|----------------|
| `_fuzz_prefix` | [rv64-v-u.S:46-48](rv64-v-u.S#L46-L48) | S-mode（虚拟地址） | vm_boot 中，进入用户态之前 | 仅 CSR 指令（rv_zicsr） |
| `_fuzz_main` | [rv64-v-u.S:189-191](rv64-v-u.S#L189-L191) | U-mode（虚拟地址） | 正常执行 | 全部指令类型 |
| `_fuzz_suffix` | [rv64-v-u.S:76-78](rv64-v-u.S#L76-L78) | S-mode（虚拟地址） | trap 处理路径中，ecall 退出前 | 全部指令类型 |

## 四、与其他模板的对比

| 特性 | p-m (Machine) | p-s (Supervisor) | p-u (User) | **v-u (Virtual-User)** |
|------|--------------|-----------------|-----------|----------------------|
| 虚拟内存 | 无 | 无 | 无 | **SV39** |
| 进入 main 的特权级 | U-mode (mret) | S-mode (mret) | U-mode (mret) | **U-mode (sret)** |
| 进入 main 的寄存器 | 随机残留 | 随机残留 | 随机残留 | **全零** (memset) |
| trap 处理 | 纯汇编 | 纯汇编 | 纯汇编 | **C 函数 (trapframe)** |
| 缺页处理 | 不存在 | 不存在 | 不存在 | **按需分配 + 随机 PTE** |
| suffix 执行位置 | S-mode (向量) | S-mode (向量) | S-mode (向量) | **S-mode (函数调用)** |
| 中断影响 | trap 到 M-mode | trap 到 M-mode | trap 到 M-mode | **直接终止测试** |
