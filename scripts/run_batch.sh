#!/bin/bash
# T.23.34: Robust batch run with proper logging
set +e

cd /Users/fundou/my_dv_proj/sv_query
OUT_DIR=/tmp/iter23_33cases
mkdir -p "$OUT_DIR"

run_case() {
    local name="$1"
    local file="$2"
    local module="$3"
    local out="$OUT_DIR/${name}.svg"
    
    if [ ! -f "$file" ]; then
        echo "SKIP|$name|file_not_found|$file"
        return 1
    fi
    
    rm -f "$out"
    timeout 90 python3 /Users/fundou/my_dv_proj/sv_query/run_cli.py visualize dataflow \
        --file "$file" \
        --module "$module" \
        --no-strict \
        --svg "$out" >"$OUT_DIR/${name}.log" 2>&1
    
    if [ -f "$out" ] && [ -s "$out" ]; then
        local size=$(stat -f%z "$out")
        echo "PASS|$name|$size|$file|$module"
    else
        local err=$(tail -3 "$OUT_DIR/${name}.log" | tr '\n' ' ' | head -c 200)
        echo "FAIL|$name|0|$file|$module|$err"
    fi
}

# All cases - using semicolon separator for safety
CASES=(
    "picorv32_wb;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32_wb"
    "picorv32_core;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32"
    "picorv32_pcpi_mul;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32_pcpi_mul"
    "picorv32_pcpi_div;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32_pcpi_div"
    "picorv32_axi;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32_axi"
    "picorv32_regs;/Users/fundou/my_dv_proj/picorv32/picorv32.v;picorv32_regs"
    "darkriscv;/Users/fundou/my_dv_proj/darkriscv/rtl/darkriscv.v;darkriscv"
    "kcpsm3;/Users/fundou/my_dv_proj/basic_verilog/pacoblaze-2.2/xilinx/kcpsm3.v;kcpsm3"
    "clacc_CLA;/Users/fundou/my_dv_proj/clacc/cla.v;CLA"
    "clacc_bs_mult;/Users/fundou/my_dv_proj/clacc/bs_mult.v;bs_mult"
    "clacc_dual_clock_fifo;/Users/fundou/my_dv_proj/clacc/dual_clock_fifo.v;dual_clock_fifo"
    "clacc_counter_5to3;/Users/fundou/my_dv_proj/clacc/counter_5to3.v;counter_5to3"
    "clacc_fa;/Users/fundou/my_dv_proj/clacc/fa.v;fa"
    "clacc_ha;/Users/fundou/my_dv_proj/clacc/ha.v;ha"
    "clacc_bs_adder;/Users/fundou/my_dv_proj/clacc/bs_adder.v;bs_adder"
    "clacc_mult_pipe2;/Users/fundou/my_dv_proj/clacc/mult_pipe2.v;mult_pipe2"
    "clacc_pe;/Users/fundou/my_dv_proj/clacc/pe.v;pe"
    "clacc_filter_spad;/Users/fundou/my_dv_proj/clacc/filter_spad.v;filter_spad"
    "tiny_gpu_decoder;/Users/fundou/my_dv_proj/tiny-gpu/src/decoder.sv;decoder"
    "tiny_gpu_registers;/Users/fundou/my_dv_proj/tiny-gpu/src/registers.sv;registers"
    "tiny_gpu_controller;/Users/fundou/my_dv_proj/tiny-gpu/src/controller.sv;controller"
    "axi_xbar;/Users/fundou/my_dv_proj/axi/src/axi_xbar.sv;axi_xbar"
    "axi_demux;/Users/fundou/my_dv_proj/axi/src/axi_demux.sv;axi_demux"
    "axi_dw_converter;/Users/fundou/my_dv_proj/axi/src/axi_dw_converter.sv;axi_dw_converter"
    "axi_fifo;/Users/fundou/my_dv_proj/axi/src/axi_fifo.sv;axi_fifo"
    "serv_serving;/Users/fundou/my_dv_proj/serv/serving/serving.v;serving"
)

PASS=0
FAIL=0
SKIP=0
RESULTS_FILE="$OUT_DIR/results.tsv"
> "$RESULTS_FILE"

for case in "${CASES[@]}"; do
    IFS=';' read -r name file module <<< "$case"
    result=$(run_case "$name" "$file" "$module")
    echo "$result" | tee -a "$RESULTS_FILE"
    
    if [[ "$result" == PASS* ]]; then
        ((PASS++))
    elif [[ "$result" == FAIL* ]]; then
        ((FAIL++))
    else
        ((SKIP++))
    fi
done

echo ""
echo "=== Summary: $PASS pass / $FAIL fail / $SKIP skip ==="