`timescale 1ns/1ps
// Shift-register delay line: carries a value alongside a pipeline.
module delay_line #(
    parameter WIDTH = 64,
    parameter DEPTH = 1          // >= 1
) (
    input  wire             clk,
    input  wire [WIDTH-1:0] d,
    output wire [WIDTH-1:0] q
);

    reg [WIDTH-1:0] sr [0:DEPTH-1];
    integer i;

    always @(posedge clk) begin
        sr[0] <= d;
        for (i = 1; i < DEPTH; i = i + 1)
            sr[i] <= sr[i-1];
    end

    assign q = sr[DEPTH-1];

endmodule
