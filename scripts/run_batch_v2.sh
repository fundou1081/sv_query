#!/bin/bash
# T.23.36: Robust batch run WITHOUT timeout command (macOS)
set +e

cd .
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
    # Use Python subprocess with timeout (more portable than GNU timeout)
    # But actually, since single cases work without timeout, just remove it
    python3 ./run_cli.py visualize dataflow \
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

# All cases - using ; separator
CASES=(
    "picorv32_wb;~/openrtl/picorv32/picorv32.v;picorv32_wb"
    "picorv32_core;~/openrtl/picorv32/picorv32.v;picorv32"
    "picorv32_pcpi_mul;~/openrtl/picorv32/picorv32.v;picorv32_pcpi_mul"
    "picorv32_pcpi_div;~/openrtl/picorv32/picorv32.v;picorv32_pcpi_div"
    "picorv32_axi;~/openrtl/picorv32/picorv32.v;picorv32_axi"
    "picorv32_regs;~/openrtl/picorv32/picorv32.v;picorv32_regs"
    "darkriscv;~/openrtl/darkriscv/rtl/darkriscv.v;darkriscv"
    "kcpsm3;~/openrtl/basic_verilog/pacoblaze-2.2/xilinx/kcpsm3.v;kcpsm3"
    "clacc_CLA;~/openrtl/clacc/cla.v;CLA"
    "clacc_bs_mult;~/openrtl/clacc/bs_mult.v;bs_mult"
    "clacc_dual_clock_fifo;~/openrtl/clacc/dual_clock_fifo.v;dual_clock_fifo"
    "clacc_counter_5to3;~/openrtl/clacc/counter_5to3.v;counter_5to3"
    "clacc_fa;~/openrtl/clacc/fa.v;fa"
    "clacc_ha;~/openrtl/clacc/ha.v;ha"
    "clacc_bs_adder;~/openrtl/clacc/bs_adder.v;bs_adder"
    "clacc_mult_pipe2;~/openrtl/clacc/mult_pipe2.v;mult_pipe2"
    "clacc_pe;~/openrtl/clacc/pe.v;pe"
    "clacc_filter_spad;~/openrtl/clacc/filter_spad.v;filter_spad"
    "tiny_gpu_decoder;~/openrtl/tiny-gpu/src/decoder.sv;decoder"
    "tiny_gpu_registers;~/openrtl/tiny-gpu/src/registers.sv;registers"
    "tiny_gpu_controller;~/openrtl/tiny-gpu/src/controller.sv;controller"
    "axi_xbar;~/openrtl/axi/src/axi_xbar.sv;axi_xbar"
    "axi_demux;~/openrtl/axi/src/axi_demux.sv;axi_demux"
    "axi_dw_converter;~/openrtl/axi/src/axi_dw_converter.sv;axi_dw_converter"
    "axi_fifo;~/openrtl/axi/src/axi_fifo.sv;axi_fifo"
    "serv_serving;~/openrtl/serv/serving/serving.v;serving"
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