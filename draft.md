# Difftest 二进制文件运行草案

全部文档的语言都使用中文

## 需求描述

我有一个二进制文件（.bin 文件，存放在 progs/ 目录下），里面有一些指令流。

我想利用这个仓库的部分代码进行 difftest：
- 让 DUT（被测设备）和 Spike（RISC-V 参考模拟器）都直接运行我的这个二进制文件
- 最后比对两者执行之后的签名（signature）

## 约束条件

- **不允许**使用 DifuzzRTL 的 template 相关逻辑
- 只需要使用该项目的 difftest 逻辑部分

## 目标

修改这个项目，使其支持直接加载并运行 .bin 文件进行 difftest，而不依赖 DifuzzRTL 的模糊测试 template 生成机制。
