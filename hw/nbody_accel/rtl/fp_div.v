`timescale 1ns/1ps
// IEEE-754 double precision divider: y = a / b   (b must be non-zero)
//
// Datapath: restoring digit-recurrence division of the 53-bit significands,
// 56 quotient bits (53 + guard + round + 1 normalization bit) plus the
// remainder as sticky, then round to nearest even.
// Each iteration of the loop is one quotient bit; with 2 bits per pipeline
// stage the operator has 28 stages (LATENCY) at the 100 MHz target.
`include "fp_common.vh"

module fp_div #(
    parameter LATENCY = 28
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        in_valid,
    input  wire [63:0] a,
    input  wire [63:0] b,
    output wire        out_valid,
    output wire [63:0] y
);

    function automatic [63:0] fp_div_comb;
        input [63:0] a;
        input [63:0] b;
        reg          sign;
        reg   [53:0] rem;      // partial remainder, < 2 * divisor
        reg   [52:0] divisor;
        reg   [55:0] q;
        reg signed [12:0] e;
        integer      i;
        begin
            sign = `FP_SIGN(a) ^ `FP_SIGN(b);
            if (`FP_IS_ZERO(a)) begin
                fp_div_comb = {sign, 63'd0};
            end else begin
                divisor = `FP_MANT(b);
                rem = {1'b0, `FP_MANT(a)};
                // quotient of ma/mb in (1/2, 2): bit 55 has weight 2^0
                q = 56'd0;
                for (i = 55; i >= 0; i = i - 1) begin
                    if (rem >= {1'b0, divisor}) begin
                        rem = rem - {1'b0, divisor};
                        q[i] = 1'b1;
                    end
                    rem = rem << 1;
                end
                e = $signed({2'b00, `FP_EXP(a)}) - $signed({2'b00, `FP_EXP(b)}) + 13'sd1023;
                if (q[55])
                    fp_div_comb = fp_round_pack(sign, q[55:3], q[2], |q[1:0] | (rem != 54'd0), e);
                else
                    fp_div_comb = fp_round_pack(sign, q[54:2], q[1], q[0] | (rem != 54'd0), e - 13'sd1);
            end
        end
    endfunction

    fp_pipe #(.WIDTH(64), .LATENCY(LATENCY)) u_pipe (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(fp_div_comb(a, b)),
        .out_valid(out_valid), .out_data(y)
    );

endmodule
