`timescale 1ns/1ps
// Fixed-latency pipeline register chain with a valid bit.
// Used after each operator's arithmetic: LATENCY register stages that
// synthesis retiming can move into the logic.
module fp_pipe #(
    parameter WIDTH   = 64,
    parameter LATENCY = 1        // >= 1
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             in_valid,
    input  wire [WIDTH-1:0] in_data,
    output wire             out_valid,
    output wire [WIDTH-1:0] out_data
);

    reg [WIDTH-1:0] data  [0:LATENCY-1];
    reg             valid [0:LATENCY-1];
    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < LATENCY; i = i + 1)
                valid[i] <= 1'b0;
        end else begin
            valid[0] <= in_valid;
            for (i = 1; i < LATENCY; i = i + 1)
                valid[i] <= valid[i-1];
        end
        data[0] <= in_data;
        for (i = 1; i < LATENCY; i = i + 1)
            data[i] <= data[i-1];
    end

    assign out_valid = valid[LATENCY-1];
    assign out_data  = data[LATENCY-1];

endmodule
