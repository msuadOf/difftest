#!/usr/bin/env bash

set -e

CONTAINER_NAME="diffuzzrtl"
IMAGE_NAME="diffuzzrtl"
HOST_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker run -itd \
        --name "${CONTAINER_NAME}" \
        -v "${HOST_DIR}:/home/host/difftest" \
        -w /home/host/difftest \
        "${IMAGE_NAME}" \
        /bin/bash
	docker exec -i "${CONTAINER_NAME}" /bin/bash -lc \
		'(cd /home/host/difftest/difuzz-rtl && ./setup.sh)'
elif ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker start "${CONTAINER_NAME}" >/dev/null
fi

# docker exec -i "${CONTAINER_NAME}" /bin/bash -lc '
# #(cd /home/host/difftest/difuzz-rtl && ./setup.sh)
# export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/RTLSim/src
# export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/src
# export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer
# export SPIKE=/home/host/difftest/difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/build/spike
# export MAKEFLAGS="-j100"
# alias make="make -j100"
# export VERILATOR_JOBS=100
# make -C /home/host/difftest/difuzz-rtl/Fuzzer \
#      SIM_BUILD=build \
#      VFILE=SmallBoomTile_v1.2_state \
#      TOPLEVEL=BoomTile \
#      NUM_ITER=100 \
#      OUT=out
# '


docker exec -i "${CONTAINER_NAME}" /bin/bash -lc '
#(cd /home/host/difftest/difuzz-rtl && ./setup.sh)
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/RTLSim/src
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer/src
export PYTHONPATH=$PYTHONPATH:/home/host/difftest/difuzz-rtl/Fuzzer
export SPIKE=/home/host/difftest/difuzz-rtl/Fuzzer/ISASim/riscv-isa-sim/build/spike
export MAKEFLAGS="-j100"
alias make="make -j100"
export VERILATOR_JOBS=100
make -C /home/host/difftest/difuzz-rtl/run_difftest \
     SIM_BUILD=build \
     VFILE=SmallBoomTile_v1.2_state \
     TOPLEVEL=BoomTile \
     NUM_ITER=100 \
     ELF_DIR=/home/host/difftest/elfs \
     MAX_CYCLES=50000 \
	 DEBUG=1 \
     OUT=out
'
