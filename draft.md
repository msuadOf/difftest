输入：progs/目录下的bin文件作为待测试的指令流
处理：使用difuzz-rtl中的部分代码，也就是difftest的部分，进行diff test测试
输出：输出比对结果

=====

## difuzz-rtl运行方法：
### 环境配置
使用diffuzzrtl镜像创建容器并进入容器：
```bash
docker run -it diffuzzrtl /bin/bash
```

配置环境，来部署工具，进入到diffuzzrtl目录下，执行如下命令安装elf2hex：
```bash
./setup.sh
```

配置环境变量：
```bash
export PYTHONPATH=$PYTHONPATH:/home/host/difuzz-rtl/Fuzzer/RTLSim/src
export PYTHONPATH=$PYTHONPATH:/home/host/difuzz-rtl/Fuzzer/src
export PYTHONPATH=$PYTHONPATH:/home/host/difuzz-rtl/Fuzzer
export SPIKE=/home/host/difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/build/spike
```

### 运行设计

SmallBoom_v1.2 CPU：
```bash
make SIM_BUILD=build \
     VFILE=SmallBoomTile_v1.2_state\
     TOPLEVEL=BoomTile \
     NUM_ITER=100 \
     OUT=out
```

### 批注
根据difuzz-rtl的运行方法，运行修改的代码
1. 修改容器启动方式：仍然使用diffuzzrtl镜像，但是在启动的时候把这个项目的目录映射进对应的目录，方便本地修改后使用镜像运行查看结果
2. 在项目根目录中，通过修改代码、新建文件夹等方式修改逻辑，使得能够单独的吃进去bin文件运行difftest
3. 通过docker的方式执行修改后的difftest
