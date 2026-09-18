`timescale 1ns/1ps
// Pair force pipeline.
//
// For one body pair (i, j) computes the six velocity deltas of the nbody
// benchmark, in the same operation order as the software:
//
//   dx = xi - xj          dy = yi - yj          dz = zi - zj         S1
//   dx2 = dx*dx           dy2 = dy*dy           dz2 = dz*dz          S2
//   s = dx2 + dy2                                                    S3
//   d2 = s + dz2                                                     S4
//   r = sqrt(d2)                                                     S5
//   den = d2 * r                                                     S6
//   mag = dt / den                    (= dt * d2 ** -1.5)            S7
//   b1m = mi * mag        b2m = mj * mag                             S8
//   dvi = (dx*b2m, dy*b2m, dz*b2m)    dvj = (dx*b1m, dy*b1m, dz*b1m) S9
//
// The caller subtracts dvi from body i's velocity and adds dvj to body j's.
// Positions are constant while pairs are processed, so pairs are independent
// and can enter the pipeline on consecutive clock cycles.
//
// Latency = 3*LAT_ADD + 4*LAT_MUL + LAT_SQRT + LAT_DIV (81 with defaults).
// dt must be stable while pairs are in flight (it is a run-time register).
module pair_force #(
    parameter LAT_ADD  = 3,
    parameter LAT_MUL  = 4,
    parameter LAT_DIV  = 28,
    parameter LAT_SQRT = 28,
    parameter TAG_W    = 8
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             in_valid,
    input  wire [TAG_W-1:0] in_tag,      // pair number, returned with the result
    input  wire [63:0]      xi, yi, zi, mi,
    input  wire [63:0]      xj, yj, zj, mj,
    input  wire [63:0]      dt,
    output wire             out_valid,
    output wire [TAG_W-1:0] out_tag,
    output wire [63:0]      dvix, dviy, dviz,
    output wire [63:0]      dvjx, dvjy, dvjz
);

    localparam T_S1 = LAT_ADD;                 // dx, dy, dz ready
    localparam T_S2 = T_S1 + LAT_MUL;          // squares ready
    localparam T_S3 = T_S2 + LAT_ADD;          // s ready
    localparam T_S4 = T_S3 + LAT_ADD;          // d2 ready
    localparam T_S5 = T_S4 + LAT_SQRT;         // r ready
    localparam T_S6 = T_S5 + LAT_MUL;          // den ready
    localparam T_S7 = T_S6 + LAT_DIV;          // mag ready
    localparam T_S8 = T_S7 + LAT_MUL;          // b1m, b2m ready
    localparam T_S9 = T_S8 + LAT_MUL;          // outputs ready
    localparam LATENCY = T_S9;

    // S1: position differences
    wire v1x, v1y, v1z;
    wire [63:0] dx, dy, dz;
    fp_add #(.LATENCY(LAT_ADD)) s1x (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .sub(1'b1),
                                     .a(xi), .b(xj), .out_valid(v1x), .y(dx));
    fp_add #(.LATENCY(LAT_ADD)) s1y (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .sub(1'b1),
                                     .a(yi), .b(yj), .out_valid(v1y), .y(dy));
    fp_add #(.LATENCY(LAT_ADD)) s1z (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .sub(1'b1),
                                     .a(zi), .b(zj), .out_valid(v1z), .y(dz));

    // S2: squares
    wire v2x, v2y, v2z;
    wire [63:0] dx2, dy2, dz2;
    fp_mul #(.LATENCY(LAT_MUL)) s2x (.clk(clk), .rst_n(rst_n), .in_valid(v1x), .a(dx), .b(dx),
                                     .out_valid(v2x), .y(dx2));
    fp_mul #(.LATENCY(LAT_MUL)) s2y (.clk(clk), .rst_n(rst_n), .in_valid(v1y), .a(dy), .b(dy),
                                     .out_valid(v2y), .y(dy2));
    fp_mul #(.LATENCY(LAT_MUL)) s2z (.clk(clk), .rst_n(rst_n), .in_valid(v1z), .a(dz), .b(dz),
                                     .out_valid(v2z), .y(dz2));

    // S3: s = dx2 + dy2 (dz2 waits)
    wire v3;
    wire [63:0] s, dz2_d;
    fp_add #(.LATENCY(LAT_ADD)) s3 (.clk(clk), .rst_n(rst_n), .in_valid(v2x), .sub(1'b0),
                                    .a(dx2), .b(dy2), .out_valid(v3), .y(s));
    delay_line #(.WIDTH(64), .DEPTH(LAT_ADD)) d_dz2 (.clk(clk), .d(dz2), .q(dz2_d));

    // S4: d2 = s + dz2
    wire v4;
    wire [63:0] d2;
    fp_add #(.LATENCY(LAT_ADD)) s4 (.clk(clk), .rst_n(rst_n), .in_valid(v3), .sub(1'b0),
                                    .a(s), .b(dz2_d), .out_valid(v4), .y(d2));

    // S5: r = sqrt(d2) (d2 waits)
    wire v5;
    wire [63:0] r, d2_d;
    fp_sqrt #(.LATENCY(LAT_SQRT)) s5 (.clk(clk), .rst_n(rst_n), .in_valid(v4), .a(d2),
                                      .out_valid(v5), .y(r));
    delay_line #(.WIDTH(64), .DEPTH(LAT_SQRT)) d_d2 (.clk(clk), .d(d2), .q(d2_d));

    // S6: den = d2 * r
    wire v6;
    wire [63:0] den;
    fp_mul #(.LATENCY(LAT_MUL)) s6 (.clk(clk), .rst_n(rst_n), .in_valid(v5), .a(d2_d), .b(r),
                                    .out_valid(v6), .y(den));

    // S7: mag = dt / den
    wire v7;
    wire [63:0] mag;
    fp_div #(.LATENCY(LAT_DIV)) s7 (.clk(clk), .rst_n(rst_n), .in_valid(v6), .a(dt), .b(den),
                                    .out_valid(v7), .y(mag));

    // S8: b1m = mi * mag, b2m = mj * mag (masses wait T_S7 cycles)
    wire [63:0] mi_d, mj_d;
    delay_line #(.WIDTH(64), .DEPTH(T_S7)) d_mi (.clk(clk), .d(mi), .q(mi_d));
    delay_line #(.WIDTH(64), .DEPTH(T_S7)) d_mj (.clk(clk), .d(mj), .q(mj_d));
    wire v8a, v8b;
    wire [63:0] b1m, b2m;
    fp_mul #(.LATENCY(LAT_MUL)) s8a (.clk(clk), .rst_n(rst_n), .in_valid(v7), .a(mi_d), .b(mag),
                                     .out_valid(v8a), .y(b1m));
    fp_mul #(.LATENCY(LAT_MUL)) s8b (.clk(clk), .rst_n(rst_n), .in_valid(v7), .a(mj_d), .b(mag),
                                     .out_valid(v8b), .y(b2m));

    // S9: velocity deltas (dx, dy, dz wait from S1 to S8)
    wire [63:0] dx_d, dy_d, dz_d;
    delay_line #(.WIDTH(64), .DEPTH(T_S8 - T_S1)) d_dx (.clk(clk), .d(dx), .q(dx_d));
    delay_line #(.WIDTH(64), .DEPTH(T_S8 - T_S1)) d_dy (.clk(clk), .d(dy), .q(dy_d));
    delay_line #(.WIDTH(64), .DEPTH(T_S8 - T_S1)) d_dz (.clk(clk), .d(dz), .q(dz_d));
    wire v9;
    wire [4:0] v9_unused;
    fp_mul #(.LATENCY(LAT_MUL)) s9a (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dx_d), .b(b2m),
                                     .out_valid(v9), .y(dvix));
    fp_mul #(.LATENCY(LAT_MUL)) s9b (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dy_d), .b(b2m),
                                     .out_valid(v9_unused[0]), .y(dviy));
    fp_mul #(.LATENCY(LAT_MUL)) s9c (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dz_d), .b(b2m),
                                     .out_valid(v9_unused[1]), .y(dviz));
    fp_mul #(.LATENCY(LAT_MUL)) s9d (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dx_d), .b(b1m),
                                     .out_valid(v9_unused[2]), .y(dvjx));
    fp_mul #(.LATENCY(LAT_MUL)) s9e (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dy_d), .b(b1m),
                                     .out_valid(v9_unused[3]), .y(dvjy));
    fp_mul #(.LATENCY(LAT_MUL)) s9f (.clk(clk), .rst_n(rst_n), .in_valid(v8a), .a(dz_d), .b(b1m),
                                     .out_valid(v9_unused[4]), .y(dvjz));

    // tag travels with the data
    delay_line #(.WIDTH(TAG_W), .DEPTH(LATENCY)) d_tag (.clk(clk), .d(in_tag), .q(out_tag));

    assign out_valid = v9;

endmodule
