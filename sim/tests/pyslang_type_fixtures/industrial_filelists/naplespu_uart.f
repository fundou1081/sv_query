// NaplesPU uart (synchronizer + uart + uart_receive + uart_transmit)
// Used for testing TL-UL deadlock detection (no valid/ready → 0 findings expected)
+incdir+~/openrtl/NaplesPU/NaplesPU/src/deploy/uart
+incdir+~/openrtl/NaplesPU/NaplesPU/src/include
~/openrtl/NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv
~/openrtl/NaplesPU/NaplesPU/src/deploy/uart/uart.sv
~/openrtl/NaplesPU/NaplesPU/src/deploy/uart/uart_receive.sv
~/openrtl/NaplesPU/NaplesPU/src/deploy/uart/uart_transmit.sv
~/openrtl/NaplesPU/NaplesPU/src/common/sync_fifo.sv
