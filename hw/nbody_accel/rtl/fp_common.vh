// IEEE-754 double precision helpers shared by the floating-point operators.
//
// Scope (see docs/design.md): zero and normal numbers, round to nearest,
// ties to even. NaN, infinity and subnormal numbers are not supported; the
// nbody workload never produces them.

`ifndef FP_COMMON_VH
`define FP_COMMON_VH

`define FP_SIGN(x)  x[63]
`define FP_EXP(x)   x[62:52]
`define FP_FRAC(x)  x[51:0]
`define FP_IS_ZERO(x) (x[62:0] == 63'd0)
// 53-bit significand with the implicit leading one
`define FP_MANT(x)  {1'b1, x[51:0]}

// Round a normalized significand and pack the result.
//   mant   : 53 bits, mant[52] == 1
//   guard  : first bit below mant
//   sticky : OR of all bits below guard
//   bexp   : biased exponent of mant (13 bits signed, must end up in 1..2046)
function automatic [63:0] fp_round_pack;
    input        sign;
    input [52:0] mant;
    input        guard;
    input        sticky;
    input signed [12:0] bexp;
    reg   [53:0] rounded;
    reg signed [12:0] e;
    begin
        // round to nearest, ties to even: increment if the dropped part is
        // more than half, or exactly half and the kept LSB is 1
        rounded = {1'b0, mant} + (guard & (sticky | mant[0]));
        e = bexp;
        if (rounded[53]) begin
            // 1.111..1 rounded up to 10.000..0: renormalize
            rounded = rounded >> 1;
            e = e + 13'sd1;
        end
        fp_round_pack = {sign, e[10:0], rounded[51:0]};
    end
endfunction

`endif
