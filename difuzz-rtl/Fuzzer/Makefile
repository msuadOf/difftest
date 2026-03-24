# Verilator COCOTB Makefile

CWD=$(shell pwd)

SIM=verilator
CMD=verilator

PYTHONPATH := $(CWD)/src:$(CWD)/RTLSim/src:$(PYTHONPATH)

TOPLEVEL_LAGN ?= verilog

# Default to RocketTile if VFILE not specified
VFILE ?= RocketTile_state

# Derive TOPLEVEL from VFILE
# For RocketTile_state -> RocketTile
# For SmallBoomTile_v1.2_state -> BoomTile (not SmallBoomTile_v1.2)
# For SmallBoomTile_v1.3_state -> BoomTile (not SmallBoomTile_v1.3)
ifneq ($(findstring SmallBoomTile,$(VFILE)),)
TOPLEVEL = BoomTile
else
TOPLEVEL = $(subst _state,,$(VFILE))
endif
VERILOG_SOURCES = $(CWD)/../Benchmarks/Verilog/$(VFILE).v
COCOTB_HDL_TIMEUNIT=1us
COCOTB_HDL_TIMEPRECISION=1us

OUT ?= output

ifdef DEBUG
    PRINT=$(DEBUG)
    PRINTF_COND=0
else
    PRINT=0
endif

ifdef MULTICORE
    MULTI=-DMULTICORE
    PLUSARGS_OUT=+OUT=$(OUT)
else
    MULTI=
    PLUSARGS_OUT=
endif

# No special includes needed for current DUT configurations
INCLUDE=

PRINTF_COND ?= 0
STOP_COND ?= 0

COMPILE_ARGS=$(MULTI) $(INCLUDE) -DPRINTF_COND=$(PRINTF_COND) -DSTOP_COND=$(STOP_COND) -Wno-PINMISSING
PLUSARGS=+DEBUG=$(PRINT) $(PLUSARGS_OUT)

MODULE?=DifuzzRTL

CUSTOM_SIM_DEPS=$(CWD)/Makefile

# Only include Makefile.sim - it will include Makefile.inc in the correct order
# and initialize PYTHON_BIN properly for cocotb 2.0+
include $(shell cocotb-config --makefiles)/Makefile.sim

sim: $(MODULE).py
