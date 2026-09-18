`timescale 1ns/1ps
// IEEE-754 double precision adder/subtractor: y = a + b (sub=0), a - b (sub=1)
//
// Datapath:
//   1. effective sign of b, pick the larger magnitude operand x
//   2. align the smaller one: 56-bit significands (53 + guard, round, sticky),
//      bits shifted out are ORed into the sticky bit
//   3. add or subtract significands
//   4. normalize: 1-bit right shift on carry out, or leading-zero count and
//      left shift after cancellation
//   5. round to nearest even
// The arithmetic is followed by LATENCY register stages (retimed by synthesis).
`include "fp_common.vh"

module fp_add #(
    parameter LATENCY = 3
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        in_valid,
    input  wire        sub,
    input  wire [63:0] a,
    input  wire [63:0] b,
    output wire        out_valid,
    output wire [63:0] y
);

    function automatic [63:0] fp_add_comb;
        input [63:0] a;
        input [63:0] b_in;
        input        sub;
        reg   [63:0] b, x, s;
        reg   [55:0] mx, ms;
        reg   [56:0] sum;
        reg   [55:0] norm;
        reg   [10:0] d;
        reg          sticky;
        reg signed [12:0] e;
        integer      lz;
        begin
            b = {b_in[63] ^ sub, b_in[62:0]};
            if (`FP_IS_ZERO(a) && `FP_IS_ZERO(b)) begin
                // +0 + -0 = +0 in round-to-nearest; -0 + -0 = -0
                fp_add_comb = {a[63] & b[63], 63'd0};
            end else if (`FP_IS_ZERO(a)) begin
                fp_add_comb = b;
            end else if (`FP_IS_ZERO(b)) begin
                fp_add_comb = a;
            end else begin
                // x = larger magnitude, s = smaller magnitude
                if (a[62:0] >= b[62:0]) begin x = a; s = b; end
                else                    begin x = b; s = a; end

                d  = `FP_EXP(x) - `FP_EXP(s);
                mx = {`FP_MANT(x), 3'b000};
                if (d >= 11'd56) begin
                    ms = 56'd1;                      // everything shifted into sticky
                end else begin
                    ms = {`FP_MANT(s), 3'b000} >> d;
                    sticky = |({`FP_MANT(s), 3'b000} & ((56'd1 << d) - 56'd1));
                    ms[0] = ms[0] | sticky;
                end
                e = $signed({2'b00, `FP_EXP(x)});

                if (x[63] == s[63]) begin
                    sum = {1'b0, mx} + {1'b0, ms};
                    if (sum[56]) begin
                        norm = sum[56:1];
                        norm[0] = norm[0] | sum[0];
                        e = e + 13'sd1;
                    end else begin
                        norm = sum[55:0];
                    end
                end else begin
                    sum = {1'b0, mx} - {1'b0, ms};
                    norm = sum[55:0];
                    // leading-zero count and normalization shift
                    lz = 0;
                    while (lz < 56 && norm[55 - lz] == 1'b0)
                        lz = lz + 1;
                    norm = norm << lz;
                    e = e - lz;
                end

                if (sum == 57'd0)
                    fp_add_comb = 64'd0;             // exact cancellation: +0
                else
                    fp_add_comb = fp_round_pack(x[63], norm[55:3], norm[2], |norm[1:0], e);
            end
        end
    endfunction

    fp_pipe #(.WIDTH(64), .LATENCY(LATENCY)) u_pipe (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(fp_add_comb(a, b, sub)),
        .out_valid(out_valid), .out_data(y)
    );

endmodule
