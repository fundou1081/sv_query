#!/bin/bash
# T.24.19: Batch run all 32 basic scenario golden_dataflow cases
set +e

cd /Users/fundou/my_dv_proj/sv_query
OUT_DIR=/tmp/iter24_32basic
mkdir -p "$OUT_DIR"

FIX_DIR="/Users/fundou/my_dv_proj/sv_query/sim/tests/fixtures/golden_mini"

# 32 cases from /tmp/iter24_modules.txt (file|module)
declare -a CASES=(
    "golden_dataflow_1_op|simple_op"
    "golden_dataflow_2_const|with_const"
    "golden_dataflow_3_slice|with_trunc"
    "golden_dataflow_4_concat|with_concat"
    "golden_dataflow_5_combined|combined"
    "golden_dataflow_6_signed|with_signed"
    "golden_dataflow_7_ternary|with_ternary"
    "golden_dataflow_8_ifelse|with_ifelse"
    "golden_dataflow_9_case|with_case"
    "golden_dataflow_10_function|with_function"
    "golden_dataflow_11_ternary_scope|ternary_scope"
    "golden_dataflow_12_ternary_complex|ternary_mixed"
    "golden_dataflow_12_ternary_mixed|ternary_mixed"
    "golden_dataflow_13_complex|complex_op"
    "golden_dataflow_14_ternary_chain|ternary_chain"
    "golden_dataflow_15_nested_ifelse|nested_ifelse"
    "golden_dataflow_16_nested_case|nested_case"
    "golden_dataflow_17_if_case_mixed|if_case_mixed"
    "golden_dataflow_18_nested_ternary|nested_ternary"
    "golden_dataflow_19_function_multi|function_multi"
    "golden_dataflow_20_ternary_scope_nested|ternary_scope_nested"
    "golden_dataflow_21_if_case_function|if_case_function"
    "golden_dataflow_22_case_if_nested|case_if_nested"
    "golden_dataflow_23_ternary_deep_chain|ternary_deep_chain"
    "golden_dataflow_24_func_recursive_nested|func_recursive_nested"
    "golden_dataflow_25_array_index|array_index"
    "golden_dataflow_26_hier_levels|level2_scale"
    "golden_dataflow_27_generate_loop|generate_loop"
    "golden_dataflow_28_func_bitmix|golden_func_bitmix"
    "golden_dataflow_29_generate_for_chain|generate_for_chain"
    "golden_dataflow_30_generate_if|generate_if_demo"
    "golden_dataflow_31_generate_case|generate_case_demo"
)

run_case() {
    local name="$1"
    local file="$2"
    local module="$3"
    local out="$OUT_DIR/${name}.svg"
    
    if [ ! -f "$file" ]; then
        echo "SKIP|$name|file_not_found"
        return 1
    fi
    
    rm -f "$out"
    python3 /Users/fundou/my_dv_proj/sv_query/run_cli.py visualize dataflow \
        --file "$file" \
        --module "$module" \
        --no-strict \
        --svg "$out" >"$OUT_DIR/${name}.log" 2>&1
    
    if [ -f "$out" ] && [ -s "$out" ]; then
        local size=$(stat -f%z "$out")
        echo "PASS|$name|$size|$module"
    else
        local err=$(tail -3 "$OUT_DIR/${name}.log" | tr '\n' ' ' | head -c 200)
        echo "FAIL|$name|0|$module|$err"
    fi
}

PASS=***
FAIL=0
SKIP=0
RESULTS_FILE="$OUT_DIR/results.tsv"
> "$RESULTS_FILE"

for case in "${CASES[@]}"; do
    IFS='|' read -r name module <<< "$case"
    file="$FIX_DIR/${name}.sv"
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