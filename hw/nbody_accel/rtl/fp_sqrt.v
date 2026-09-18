`timescale 1ns/1ps
// IEEE-754 double precision square root: y = sqrt(a)   (a must be >= 0)
//
// Datapath:
//   1. make the unbiased exponent even (shift the significand left by one
//      if it is odd), result exponent = exponent / 2
//   2. restoring digit-recurrence integer square root of the significand
//      scaled to 112 bits: 56 root bits, the remainder is the sticky bit
//   3. round to nearest even (an exact tie cannot occur for sqrt)
// One root bit per iteration; 2 bits per pipeline stage gives 28 stages
// (LATENCY) at the 100 MHz target.
`include "fp_common.vh"

module fp_sqrt #(
    parameter LATENCY = 28
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        in_valid,
    input  wire [63:0] a,
    output wire        out_valid,
    output wire [63:0] y
);

    function automatic [63:0] fp_sqrt_comb;
        input [63:0] a;
        reg  [111:0] m;         // radicand: significand << 58 (or << 59)
        reg   [57:0] rem;
        reg   [55:0] root;
        reg   [57:0] trial;
        reg signed [12:0] e;
        integer      i;
        begin
            if (`FP_IS_ZERO(a)) begin
                fp_sqrt_comb = a;                    // sqrt(+-0) = +-0
            end else begin
                e = $signed({2'b00, `FP_EXP(a)}) - 13'sd1023;
                if (e[0]) begin
                    m = {`FP_MANT(a), 59'd0};        // odd exponent: one more bit
                    e = e - 13'sd1;
                end else begin
                    m = {1'b0, `FP_MANT(a), 58'd0};
                end
                // integer square root: root in [2^55, 2^56)
                rem  = 58'd0;
                root = 56'd0;
                for (i = 55; i >= 0; i = i - 1) begin
                    rem   = {rem[55:0], m[2*i+1], m[2*i]};
                    trial = {root, 2'b01};
                    if (rem >= trial) begin
                        rem  = rem - trial;
                        root = {root[54:0], 1'b1};
                    end else begin
                        root = {root[54:0], 1'b0};
                    end
                end
                fp_sqrt_comb = fp_round_pack(1'b0, root[55:3], root[2], |root[1:0] | (rem != 58'd0),
                                             (e >>> 1) + 13'sd1023);
            end
        end
    endfunction

    fp_pipe #(.WIDTH(64), .LATENCY(LATENCY)) u_pipe (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(fp_sqrt_comb(a)),
        .out_valid(out_valid), .out_data(y)
    );

endmodule
