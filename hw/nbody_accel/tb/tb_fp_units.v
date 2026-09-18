// Unit test of the floating-point operators against Python (IEEE-754)
// reference results from model/gen_fp_vectors.py.
//
// One vector enters each operator per clock cycle; results are checked when
// they leave the pipeline, bit for bit.
`timescale 1ns/1ps

module tb_fp_units;

    localparam MAXV = 200000;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;                      // 100 MHz

    // vector memories: add has 4 fields, mul/div 3, sqrt 2
    reg [63:0] add_v  [0:4*MAXV-1];
    reg [63:0] mul_v  [0:3*MAXV-1];
    reg [63:0] div_v  [0:3*MAXV-1];
    reg [63:0] sqrt_v [0:2*MAXV-1];
    integer n_add, n_mul, n_div, n_sqrt;

    // one driver/checker per operator
    integer i_add = 0, i_mul = 0, i_div = 0, i_sqrt = 0;      // next input
    integer o_add = 0, o_mul = 0, o_div = 0, o_sqrt = 0;      // next expected output
    integer err_add = 0, err_mul = 0, err_div = 0, err_sqrt = 0;

    reg        v_add = 0, v_mul = 0, v_div = 0, v_sqrt = 0;
    reg        sub = 0;
    reg [63:0] a_add, b_add, a_mul, b_mul, a_div, b_div, a_sqrt;
    wire       ov_add, ov_mul, ov_div, ov_sqrt;
    wire [63:0] y_add, y_mul, y_div, y_sqrt;

    fp_add  u_add  (.clk(clk), .rst_n(rst_n), .in_valid(v_add),  .sub(sub), .a(a_add), .b(b_add),
                    .out_valid(ov_add),  .y(y_add));
    fp_mul  u_mul  (.clk(clk), .rst_n(rst_n), .in_valid(v_mul),  .a(a_mul), .b(b_mul),
                    .out_valid(ov_mul),  .y(y_mul));
    fp_div  u_div  (.clk(clk), .rst_n(rst_n), .in_valid(v_div),  .a(a_div), .b(b_div),
                    .out_valid(ov_div),  .y(y_div));
    fp_sqrt u_sqrt (.clk(clk), .rst_n(rst_n), .in_valid(v_sqrt), .a(a_sqrt),
                    .out_valid(ov_sqrt), .y(y_sqrt));

    function integer count_lines;
        input [8*64-1:0] path;
        integer fd, c, n;
        begin
            n = 0;
            fd = $fopen(path, "r");
            if (fd == 0) begin
                $display("cannot open %0s", path);
                $finish;
            end
            c = $fgetc(fd);
            while (c != -1) begin
                if (c == 10) n = n + 1;
                c = $fgetc(fd);
            end
            $fclose(fd);
            count_lines = n;
        end
    endfunction

    initial begin
        n_add  = count_lines("vectors/add.hex");
        n_mul  = count_lines("vectors/mul.hex");
        n_div  = count_lines("vectors/div.hex");
        n_sqrt = count_lines("vectors/sqrt.hex");
        $readmemh("vectors/add.hex",  add_v);
        $readmemh("vectors/mul.hex",  mul_v);
        $readmemh("vectors/div.hex",  div_v);
        $readmemh("vectors/sqrt.hex", sqrt_v);
        $display("vectors: add=%0d mul=%0d div=%0d sqrt=%0d", n_add, n_mul, n_div, n_sqrt);
        repeat (3) @(posedge clk);
        rst_n <= 1'b1;
    end

    // drive inputs
    always @(posedge clk) if (rst_n) begin
        v_add <= (i_add < n_add);
        if (i_add < n_add) begin
            sub   <= add_v[4*i_add][0];
            a_add <= add_v[4*i_add+1];
            b_add <= add_v[4*i_add+2];
            i_add <= i_add + 1;
        end
        v_mul <= (i_mul < n_mul);
        if (i_mul < n_mul) begin
            a_mul <= mul_v[3*i_mul]; b_mul <= mul_v[3*i_mul+1]; i_mul <= i_mul + 1;
        end
        v_div <= (i_div < n_div);
        if (i_div < n_div) begin
            a_div <= div_v[3*i_div]; b_div <= div_v[3*i_div+1]; i_div <= i_div + 1;
        end
        v_sqrt <= (i_sqrt < n_sqrt);
        if (i_sqrt < n_sqrt) begin
            a_sqrt <= sqrt_v[2*i_sqrt]; i_sqrt <= i_sqrt + 1;
        end
    end

    // check outputs
    always @(posedge clk) if (rst_n) begin
        if (ov_add) begin
            if (y_add !== add_v[4*o_add+3]) begin
                err_add = err_add + 1;
                if (err_add <= 5)
                    $display("ADD mismatch #%0d: sub=%0d a=%h b=%h got=%h exp=%h", o_add,
                             add_v[4*o_add][0], add_v[4*o_add+1], add_v[4*o_add+2], y_add, add_v[4*o_add+3]);
            end
            o_add = o_add + 1;
        end
        if (ov_mul) begin
            if (y_mul !== mul_v[3*o_mul+2]) begin
                err_mul = err_mul + 1;
                if (err_mul <= 5)
                    $display("MUL mismatch #%0d: a=%h b=%h got=%h exp=%h", o_mul,
                             mul_v[3*o_mul], mul_v[3*o_mul+1], y_mul, mul_v[3*o_mul+2]);
            end
            o_mul = o_mul + 1;
        end
        if (ov_div) begin
            if (y_div !== div_v[3*o_div+2]) begin
                err_div = err_div + 1;
                if (err_div <= 5)
                    $display("DIV mismatch #%0d: a=%h b=%h got=%h exp=%h", o_div,
                             div_v[3*o_div], div_v[3*o_div+1], y_div, div_v[3*o_div+2]);
            end
            o_div = o_div + 1;
        end
        if (ov_sqrt) begin
            if (y_sqrt !== sqrt_v[2*o_sqrt+1]) begin
                err_sqrt = err_sqrt + 1;
                if (err_sqrt <= 5)
                    $display("SQRT mismatch #%0d: a=%h got=%h exp=%h", o_sqrt,
                             sqrt_v[2*o_sqrt], y_sqrt, sqrt_v[2*o_sqrt+1]);
            end
            o_sqrt = o_sqrt + 1;
        end
        if (o_add == n_add && o_mul == n_mul && o_div == n_div && o_sqrt == n_sqrt) begin
            $display("fp_add : %0d vectors, %0d errors", n_add, err_add);
            $display("fp_mul : %0d vectors, %0d errors", n_mul, err_mul);
            $display("fp_div : %0d vectors, %0d errors", n_div, err_div);
            $display("fp_sqrt: %0d vectors, %0d errors", n_sqrt, err_sqrt);
            if (err_add + err_mul + err_div + err_sqrt == 0) $display("PASS");
            else                                             $display("FAIL");
            $finish;
        end
    end

endmodule
