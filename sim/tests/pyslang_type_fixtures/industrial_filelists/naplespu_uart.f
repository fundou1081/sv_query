// NaplesPU uart (synchronizer + uart + uart_receive + uart_transmit)
// Used for testing TL-UL deadlock detection (no valid/ready → 0 findings expected)
+incdir+${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/deploy/uart
+incdir+${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/include
${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv
${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/deploy/uart/uart.sv
${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/deploy/uart/uart_receive.sv
${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/deploy/uart/uart_transmit.sv
${SVQ_OPENRTL_ROOT}/NaplesPU/NaplesPU/src/common/sync_fifo.sv
