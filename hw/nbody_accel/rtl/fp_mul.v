`timescale 1ns/1ps
// IEEE-754 double precision multiplier: y = a * b
//
// Datapath: 53x53-bit significand product (106 bits), 1-bit normalization,
// round to nearest even, exponent = ea + eb - bias.
// The arithmetic is followed by LATENCY register stages; synthesis retiming
// spreads them through the multiplier (DSP blocks) to meet the clock target.
`include "fp_common.vh"

module fp_mul #(
    parameter LATENCY = 4
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        in_valid,
    input  wire [63:0] a,
    input  wire [63:0] b,
    output wire        out_valid,
    output wire [63:0] y
);

    function automatic [63:0] fp_mul_comb;
        input [63:0] a;
        input [63:0] b;
        reg          sign;
        reg  [105:0] p;
        reg signed [12:0] e;
        begin
            sign = `FP_SIGN(a) ^ `FP_SIGN(b);
            if (`FP_IS_ZERO(a) || `FP_IS_ZERO(b)) begin
                fp_mul_comb = {sign, 63'd0};
            end else begin
                p = `FP_MANT(a) * `FP_MANT(b);        // in [2^104, 2^106)
                e = $signed({2'b00, `FP_EXP(a)}) + $signed({2'b00, `FP_EXP(b)}) - 13'sd1023;
                if (p[105])
                    fp_mul_comb = fp_round_pack(sign, p[105:53], p[52], |p[51:0], e + 13'sd1);
                else
                    fp_mul_comb = fp_round_pack(sign, p[104:52], p[51], |p[50:0], e);
            end
        end
    endfunction

    fp_pipe #(.WIDTH(64), .LATENCY(LATENCY)) u_pipe (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(fp_mul_comb(a, b)),
        .out_valid(out_valid), .out_data(y)
    );

endmodule
