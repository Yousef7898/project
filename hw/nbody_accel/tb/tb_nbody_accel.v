`timescale 1ns/1ps
// System test of nbody_accel_top, driven only through its MMIO registers
// (like the host driver would).
//
//   1. check the ID register
//   2. write NUM_BODIES, NUM_STEPS, DT and every body register
//   3. set START, wait for STATUS.DONE (or irq_done)
//   4. read every body register back and compare with the golden model
//      (model/nbody_golden.py), bit for bit
//   5. report clock cycles per time step (CYCLES register)
//
// usage: vvp tb.vvp +vec=vectors/sys_benchmark.hex
module tb_nbody_accel;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;                     // 100 MHz

    reg  [15:0] mmio_addr = 16'd0;
    reg         mmio_wen = 1'b0, mmio_ren = 1'b0;
    reg  [63:0] mmio_wdata = 64'd0;
    wire [63:0] mmio_rdata;
    wire        irq_done;

    nbody_accel_top dut (
        .clk(clk), .rst_n(rst_n),
        .mmio_addr(mmio_addr), .mmio_wen(mmio_wen), .mmio_wdata(mmio_wdata),
        .mmio_ren(mmio_ren), .mmio_rdata(mmio_rdata), .irq_done(irq_done)
    );

    // host-side register access tasks
    task mmio_write(input [15:0] addr, input [63:0] data);
        begin
            @(negedge clk);
            mmio_addr = addr; mmio_wdata = data; mmio_wen = 1'b1;
            @(negedge clk);
            mmio_wen = 1'b0;
        end
    endtask

    task mmio_read(input [15:0] addr, output [63:0] data);
        begin
            @(negedge clk);
            mmio_addr = addr; mmio_ren = 1'b1;
            @(negedge clk);
            mmio_ren = 1'b0;
            data = mmio_rdata;
        end
    endtask

    function [15:0] body_addr(input integer b, input integer f);
        body_addr = 16'h1000 + 16'h40 * b + 8 * f;
    endfunction

    reg [63:0] vec [0:3 + 14*16 - 1];
    reg [8*128-1:0] vecfile;
    integer n, steps, b, f, errors;
    reg [63:0] rd, t_start, t_end;
    time run_start;

    initial begin
        if (!$value$plusargs("vec=%s", vecfile))
            vecfile = "vectors/sys_benchmark.hex";
        $readmemh(vecfile, vec);
        n = vec[0];
        steps = vec[1];
        $display("system test %0s: N=%0d steps=%0d dt=%h", vecfile, n, steps, vec[2]);

        repeat (3) @(posedge clk);
        rst_n = 1'b1;

        mmio_read(16'h0000, rd);
        if (rd !== 64'h4E424F4459414343) begin
            $display("FAIL: bad ID %h", rd);
            $finish;
        end

        // program the run
        mmio_write(16'h0018, n);
        mmio_write(16'h0020, steps);
        mmio_write(16'h0028, vec[2]);
        for (b = 0; b < n; b = b + 1)
            for (f = 0; f < 7; f = f + 1)
                mmio_write(body_addr(b, f), vec[3 + 7*b + f]);

        // start and wait for completion
        run_start = $time;
        mmio_write(16'h0008, 64'd1);
        mmio_read(16'h0010, rd);
        if (rd[0] !== 1'b1) begin
            $display("FAIL: BUSY not set after START (status=%h)", rd);
            $finish;
        end
        wait (irq_done === 1'b1);
        @(negedge clk);

        mmio_read(16'h0010, rd);
        if (rd[1:0] !== 2'b10) begin
            $display("FAIL: STATUS after run = %h", rd);
            $finish;
        end
        mmio_read(16'h0030, rd);
        if (rd !== steps) begin
            $display("FAIL: STEPS_DONE = %0d", rd);
            $finish;
        end

        // compare the final state with the golden model
        errors = 0;
        for (b = 0; b < n; b = b + 1)
            for (f = 0; f < 7; f = f + 1) begin
                mmio_read(body_addr(b, f), rd);
                if (rd !== vec[3 + 7*n + 7*b + f]) begin
                    errors = errors + 1;
                    if (errors <= 10)
                        $display("  mismatch body %0d field %0d: got %h expected %h",
                                 b, f, rd, vec[3 + 7*n + 7*b + f]);
                end
            end

        mmio_read(16'h0038, rd);
        $display("  cycles: %0d total, %0.1f per step (N=%0d, %0d pairs)",
                 rd, rd * 1.0 / steps, n, n * (n - 1) / 2);
        $display("  at 100 MHz: %0.3f us per step", rd * 10.0e-3 / steps);
        if (errors == 0)
            $display("PASS: %0d values bit-identical to the golden model", 7 * n);
        else
            $display("FAIL: %0d of %0d values differ", errors, 7 * n);
        $finish;
    end

    // safety timeout
    initial begin
        #(64'd50_000_000_000);
        $display("FAIL: timeout");
        $finish;
    end

endmodule
