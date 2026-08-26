#!/bin/bash
# T.23.27: Batch run all verifiable cases (corrected paths)
# Date: 2026-08-26 08:42 GMT+8
# User request: 再重跑一下之前的33个case，把生成的图发给我

set +e  # Don't exit on error

cd ~/my_dv_proj/sv_query

OUT_DIR=/tmp/iter23_33cases
mkdir -p $OUT_DIR

# Cases with verified paths (30+ cases)
declare -a CASES=(
    # picorv32 family (7) - all in one file
    "picorv32_wb|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32_wb"
    "picorv32_core|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32"
    "picorv32_pcpi_mul|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32_pcpi_mul"
    "picorv32_pcpi_div|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32_pcpi_div"
    "picorv32_axi|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32_axi"
    "picorv32_regs|/Users/fundou/my_dv_proj/picorv32/picorv32.v|picorv32_regs"
    # Other RISC-V / CPUs (2)
    "darkriscv|/Users/fundou/my_dv_proj/darkriscv/rtl/darkriscv.v|darkriscv"
    "kcpsm3|/Users/fundou/my_dv_proj/basic_verilog/pacoblaze-2.2/xilinx/kcpsm3.v|kcpsm3"
    # clacc (10)
    "clacc_CLA|/Users/fundou/my_dv_proj/clacc/cla.v|CLA"
    "clacc_bs_mult|/Users/fundou/my_dv_proj/clacc/bs_mult.v|bs_mult"
    "clacc_dual_clock_fifo|/Users/fundou/my_dv_proj/clacc/dual_clock_fifo.v|dual_clock_fifo"
    "clacc_counter_5to3|/Users/fundou/my_dv_proj/clacc/counter_5to3.v|counter_5to3"
    "clacc_fa|/Users/fundou/my_dv_proj/clacc/fa.v|fa"
    "clacc_ha|/Users/fundou/my_dv_proj/clacc/ha.v|ha"
    "clacc_bs_adder|/Users/fundou/my_dv_proj/clacc/bs_adder.v|bs_adder"
    "clacc_mult_pipe2|/Users/fundou/my_dv_proj/clacc/mult_pipe2.v|mult_pipe2"
    "clacc_pe|/Users/fundou/my_dv_proj/clacc/pe.v|pe"
    "clacc_filter_spad|/Users/fundou/my_dv_proj/clacc/filter_spad.v|filter_spad"
    # tiny-gpu (3) - SystemVerilog
    "tiny_gpu_decoder|/Users/fundou/my_dv_proj/tiny-gpu/src/decoder.sv|decoder"
    "tiny_gpu_registers|/Users/fundou/my_dv_proj/tiny-gpu/src/registers.sv|registers"
    "tiny_gpu_controller|/Users/fundou/my_dv_proj/tiny-gpu/src/controller.sv|controller"
    # AXI (5)
    "axi_xbar|/Users/fundou/my_dv_proj/axi/src/axi_xbar.sv|axi_xbar"
    "axi_demux|/Users/fundou/my_dv_proj/axi/src/axi_demux.sv|axi_demux"
    "axi_dw_converter|/Users/fundou/my_dv_proj/axi/src/axi_dw_converter.sv|axi_dw_converter"
    "axi_fifo|/Users/fundou/my_dv_proj/axi/src/axi_fifo.sv|axi_fifo"
    "axi_ram|/Users/fundou/my_dv_proj/axi/src/axi_ram.sv|axi_ram"
    # serv (1)
    "serv_serving|/Users/fundou/my_dv_proj/serv/serving/serving.v|serving"
    # serv is a top, use serving.v
    # Other from basic_verilog (5)
    "pacoblaze|/Users/fundou/my_dv_proj/basic_verilog/pacoblaze-2.2/xilinx/pacoblaze.v|pacoblaze"
    "aes_128|/Users/fundou/my_dv_proj/basic_verilog/aes_128.v|aes_128"
    "des|/Users/fundou/my_dv_proj/basic_verilog/des.v|des"
    "uart|/Users/fundou/my_dv_proj/basic_verilog/uart.v|uart"
    "sha512|/Users/fundou/my_dv_proj/basic_verilog/sha512.v|sha512"
)

echo "=== Running ${#CASES[@]} cases ==="
PASS=0
FAIL=0
SKIP=0
declare -a FAILED_NAMES
declare -a PASSED_NAMES

for case in "${CASES[@]}"; do
    IFS='|' read -r name file module <<< "$case"
    
    if [ ! -f "$file" ]; then
        echo "⏭️  SKIP [$name]: file not found ($file)"
        SKIP=$((SKIP + 1))
        continue
    fi
    
    OUT="$OUT_DIR/${name}.svg"
    echo -n "▶️  RUN [$name]..."
    
    timeout 60 python3 run_cli.py visualize dataflow \
        --file "$file" \
        --module "$module" \
        --no-strict \
        --svg "$OUT" >/dev/null 2>&1
    
    if [ -f "$OUT" ] && [ -s "$OUT" ]; then
        SIZE=$(stat -f%z "$OUT")
        echo " ✅ PASS (${SIZE}B)"
        PASS=$((PASS + 1))
        PASSED_NAMES+=("$name")
    else
        echo " ❌ FAIL"
        FAIL=$((FAIL + 1))
        FAILED_NAMES+=("$name")
    fi
done

echo ""
echo "=== Summary: $PASS pass / $FAIL fail / $SKIP skip ==="
echo ""
if [ ${#FAILED_NAMES[@]} -gt 0 ]; then
    echo "Failed cases:"
    for f in "${FAILED_NAMES[@]}"; do
        echo "  ❌ $f"
    done
fi
echo ""
echo "=== Saving passed list ==="
printf '%s\n' "${PASSED_NAMES[@]}" > /tmp/iter23_passed.txt
echo "Saved to /tmp/iter23_passed.txt"