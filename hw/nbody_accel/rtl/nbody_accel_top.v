`timescale 1ns/1ps
// nbody force accelerator: top level.
//
// Contains the memory-mapped register block (host interface, PCIe BAR0 view),
// the body state memory, the controller FSM, the pair_force pipeline, the
// velocity accumulator and the position updater. See docs/design.md.
//
// Register map (64-bit registers):
//   0x0000 ID          R   "NBODYACC"
//   0x0008 CTRL        W   bit0 START
//   0x0010 STATUS      R   bit0 BUSY, bit1 DONE
//   0x0018 NUM_BODIES  RW  2..MAX_BODIES
//   0x0020 NUM_STEPS   RW  32 bits
//   0x0028 DT          RW  IEEE-754 double
//   0x0030 STEPS_DONE  R   progress
//   0x0038 CYCLES      R   clock cycles of the last run (performance counter)
//   0x1000 + 0x40*b + 8*f  BODY[b] field f: 0 x, 1 y, 2 z, 3 vx, 4 vy, 5 vz, 6 m
module nbody_accel_top #(
    parameter MAX_BODIES = 16,
    parameter LAT_ADD    = 3,
    parameter LAT_MUL    = 4,
    parameter LAT_DIV    = 28,
    parameter LAT_SQRT   = 28
) (
    input  wire        clk,
    input  wire        rst_n,
    // MMIO (BAR0)
    input  wire [15:0] mmio_addr,
    input  wire        mmio_wen,
    input  wire [63:0] mmio_wdata,
    input  wire        mmio_ren,
    output reg  [63:0] mmio_rdata,
    output wire        irq_done
);

    localparam [63:0] ID_VALUE = 64'h4E424F4459414343;   // "NBODYACC"
    localparam BODY_BASE = 16'h1000;

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------
    reg [63:0] bx  [0:MAX_BODIES-1];
    reg [63:0] by  [0:MAX_BODIES-1];
    reg [63:0] bz  [0:MAX_BODIES-1];
    reg [63:0] bvx [0:MAX_BODIES-1];
    reg [63:0] bvy [0:MAX_BODIES-1];
    reg [63:0] bvz [0:MAX_BODIES-1];
    reg [63:0] bm  [0:MAX_BODIES-1];

    reg [4:0]  num_bodies;
    reg [31:0] num_steps;
    reg [63:0] dt;
    reg [31:0] steps_done;
    reg [63:0] cycles;
    reg        busy, done;

    // controller
    localparam S_IDLE     = 4'd0,
               S_FEED     = 4'd1,
               S_DRAIN    = 4'd2,
               S_ACC_GO   = 4'd3,
               S_ACC_WAIT = 4'd4,
               S_POS_MUL  = 4'd5,
               S_POS_MULW = 4'd6,
               S_POS_ADD  = 4'd7,
               S_POS_ADDW = 4'd8,
               S_STEP_END = 4'd9;
    reg [3:0]  state;
    reg [4:0]  pi, pj;           // current pair (i < j)
    reg [6:0]  k;                // current pair number
    reg [6:0]  num_pairs;
    reg [7:0]  received;         // pair results received from the pipeline
    reg [4:0]  pb;               // current body in the position update

    // ------------------------------------------------------------------
    // pair_force pipeline
    // ------------------------------------------------------------------
    reg         pf_valid;
    reg  [7:0]  pf_tag;
    reg  [63:0] pf_xi, pf_yi, pf_zi, pf_mi, pf_xj, pf_yj, pf_zj, pf_mj;
    wire        pf_out_valid;
    wire [7:0]  pf_out_tag;
    wire [63:0] pf_dvix, pf_dviy, pf_dviz, pf_dvjx, pf_dvjy, pf_dvjz;

    pair_force #(.LAT_ADD(LAT_ADD), .LAT_MUL(LAT_MUL), .LAT_DIV(LAT_DIV),
                 .LAT_SQRT(LAT_SQRT), .TAG_W(8)) u_pair (
        .clk(clk), .rst_n(rst_n),
        .in_valid(pf_valid), .in_tag(pf_tag),
        .xi(pf_xi), .yi(pf_yi), .zi(pf_zi), .mi(pf_mi),
        .xj(pf_xj), .yj(pf_yj), .zj(pf_zj), .mj(pf_mj),
        .dt(dt),
        .out_valid(pf_out_valid), .out_tag(pf_out_tag),
        .dvix(pf_dvix), .dviy(pf_dviy), .dviz(pf_dviz),
        .dvjx(pf_dvjx), .dvjy(pf_dvjy), .dvjz(pf_dvjz)
    );

    // pair result buffer (indexed by pair number)
    localparam MAX_PAIRS = MAX_BODIES * (MAX_BODIES - 1) / 2;
    reg [63:0] r_ix [0:MAX_PAIRS-1];
    reg [63:0] r_iy [0:MAX_PAIRS-1];
    reg [63:0] r_iz [0:MAX_PAIRS-1];
    reg [63:0] r_jx [0:MAX_PAIRS-1];
    reg [63:0] r_jy [0:MAX_PAIRS-1];
    reg [63:0] r_jz [0:MAX_PAIRS-1];

    // ------------------------------------------------------------------
    // velocity accumulator: 6 adders (body i: v - dvi, body j: v + dvj)
    // ------------------------------------------------------------------
    reg         acc_valid;
    reg  [63:0] acc_vix, acc_viy, acc_viz, acc_vjx, acc_vjy, acc_vjz;
    reg  [63:0] acc_dix, acc_diy, acc_diz, acc_djx, acc_djy, acc_djz;
    wire [5:0]  acc_ov;
    wire [63:0] acc_nix, acc_niy, acc_niz, acc_njx, acc_njy, acc_njz;

    fp_add #(.LATENCY(LAT_ADD)) a_ix (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b1),
                                      .a(acc_vix), .b(acc_dix), .out_valid(acc_ov[0]), .y(acc_nix));
    fp_add #(.LATENCY(LAT_ADD)) a_iy (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b1),
                                      .a(acc_viy), .b(acc_diy), .out_valid(acc_ov[1]), .y(acc_niy));
    fp_add #(.LATENCY(LAT_ADD)) a_iz (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b1),
                                      .a(acc_viz), .b(acc_diz), .out_valid(acc_ov[2]), .y(acc_niz));
    fp_add #(.LATENCY(LAT_ADD)) a_jx (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b0),
                                      .a(acc_vjx), .b(acc_djx), .out_valid(acc_ov[3]), .y(acc_njx));
    fp_add #(.LATENCY(LAT_ADD)) a_jy (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b0),
                                      .a(acc_vjy), .b(acc_djy), .out_valid(acc_ov[4]), .y(acc_njy));
    fp_add #(.LATENCY(LAT_ADD)) a_jz (.clk(clk), .rst_n(rst_n), .in_valid(acc_valid), .sub(1'b0),
                                      .a(acc_vjz), .b(acc_djz), .out_valid(acc_ov[5]), .y(acc_njz));

    // ------------------------------------------------------------------
    // position update: 3 multipliers (dt * v) then 3 adders (pos + dt*v)
    // ------------------------------------------------------------------
    reg         pm_valid, pa_valid;
    reg  [63:0] pm_vx, pm_vy, pm_vz;
    reg  [63:0] pa_x, pa_y, pa_z, pa_px, pa_py, pa_pz;
    wire [2:0]  pm_ov, pa_ov;
    wire [63:0] pm_px, pm_py, pm_pz, pa_nx, pa_ny, pa_nz;

    fp_mul #(.LATENCY(LAT_MUL)) m_x (.clk(clk), .rst_n(rst_n), .in_valid(pm_valid), .a(dt), .b(pm_vx),
                                     .out_valid(pm_ov[0]), .y(pm_px));
    fp_mul #(.LATENCY(LAT_MUL)) m_y (.clk(clk), .rst_n(rst_n), .in_valid(pm_valid), .a(dt), .b(pm_vy),
                                     .out_valid(pm_ov[1]), .y(pm_py));
    fp_mul #(.LATENCY(LAT_MUL)) m_z (.clk(clk), .rst_n(rst_n), .in_valid(pm_valid), .a(dt), .b(pm_vz),
                                     .out_valid(pm_ov[2]), .y(pm_pz));
    fp_add #(.LATENCY(LAT_ADD)) p_x (.clk(clk), .rst_n(rst_n), .in_valid(pa_valid), .sub(1'b0),
                                     .a(pa_x), .b(pa_px), .out_valid(pa_ov[0]), .y(pa_nx));
    fp_add #(.LATENCY(LAT_ADD)) p_y (.clk(clk), .rst_n(rst_n), .in_valid(pa_valid), .sub(1'b0),
                                     .a(pa_y), .b(pa_py), .out_valid(pa_ov[1]), .y(pa_ny));
    fp_add #(.LATENCY(LAT_ADD)) p_z (.clk(clk), .rst_n(rst_n), .in_valid(pa_valid), .sub(1'b0),
                                     .a(pa_z), .b(pa_pz), .out_valid(pa_ov[2]), .y(pa_nz));

    // ------------------------------------------------------------------
    // MMIO address decode
    // ------------------------------------------------------------------
    wire [15:0] body_off   = mmio_addr - BODY_BASE;
    wire        body_hit   = (mmio_addr >= BODY_BASE) &&
                             (body_off < MAX_BODIES * 16'h40) &&
                             (body_off[2:0] == 3'd0) &&
                             (body_off[5:3] <= 3'd6);
    wire [4:0]  body_idx   = body_off[10:6];
    wire [2:0]  body_field = body_off[5:3];

    wire [5:0]  last_body_minus = num_bodies - 5'd1;

    // ------------------------------------------------------------------
    // MMIO read
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (mmio_ren) begin
            if (body_hit) begin
                case (body_field)
                    3'd0: mmio_rdata <= bx[body_idx];
                    3'd1: mmio_rdata <= by[body_idx];
                    3'd2: mmio_rdata <= bz[body_idx];
                    3'd3: mmio_rdata <= bvx[body_idx];
                    3'd4: mmio_rdata <= bvy[body_idx];
                    3'd5: mmio_rdata <= bvz[body_idx];
                    default: mmio_rdata <= bm[body_idx];
                endcase
            end else begin
                case (mmio_addr)
                    16'h0000: mmio_rdata <= ID_VALUE;
                    16'h0010: mmio_rdata <= {62'd0, done, busy};
                    16'h0018: mmio_rdata <= {59'd0, num_bodies};
                    16'h0020: mmio_rdata <= {32'd0, num_steps};
                    16'h0028: mmio_rdata <= dt;
                    16'h0030: mmio_rdata <= {32'd0, steps_done};
                    16'h0038: mmio_rdata <= cycles;
                    default:  mmio_rdata <= 64'd0;
                endcase
            end
        end
    end

    assign irq_done = done;

    // ------------------------------------------------------------------
    // Controller, MMIO write, state memory
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            busy       <= 1'b0;
            done       <= 1'b0;
            num_bodies <= 5'd2;
            num_steps  <= 32'd0;
            dt         <= 64'd0;
            steps_done <= 32'd0;
            cycles     <= 64'd0;
            pf_valid   <= 1'b0;
            acc_valid  <= 1'b0;
            pm_valid   <= 1'b0;
            pa_valid   <= 1'b0;
            received   <= 8'd0;
        end else begin
            // one-cycle strobes
            pf_valid  <= 1'b0;
            acc_valid <= 1'b0;
            pm_valid  <= 1'b0;
            pa_valid  <= 1'b0;

            if (busy)
                cycles <= cycles + 64'd1;

            // host writes (configuration and body state only while idle)
            if (mmio_wen && !busy) begin
                if (body_hit) begin
                    case (body_field)
                        3'd0: bx[body_idx]  <= mmio_wdata;
                        3'd1: by[body_idx]  <= mmio_wdata;
                        3'd2: bz[body_idx]  <= mmio_wdata;
                        3'd3: bvx[body_idx] <= mmio_wdata;
                        3'd4: bvy[body_idx] <= mmio_wdata;
                        3'd5: bvz[body_idx] <= mmio_wdata;
                        default: bm[body_idx] <= mmio_wdata;
                    endcase
                end else begin
                    case (mmio_addr)
                        16'h0018: num_bodies <= mmio_wdata[4:0];
                        16'h0020: num_steps  <= mmio_wdata[31:0];
                        16'h0028: dt         <= mmio_wdata;
                        default: ;
                    endcase
                end
            end

            // pipeline results go to the result buffer
            if (pf_out_valid) begin
                r_ix[pf_out_tag] <= pf_dvix;
                r_iy[pf_out_tag] <= pf_dviy;
                r_iz[pf_out_tag] <= pf_dviz;
                r_jx[pf_out_tag] <= pf_dvjx;
                r_jy[pf_out_tag] <= pf_dvjy;
                r_jz[pf_out_tag] <= pf_dvjz;
                received <= received + 8'd1;
            end

            case (state)
            S_IDLE: begin
                if (mmio_wen && mmio_addr == 16'h0008 && mmio_wdata[0]) begin
                    done       <= 1'b0;
                    steps_done <= 32'd0;
                    cycles     <= 64'd0;
                    num_pairs  <= ({3'd0, num_bodies} * ({3'd0, num_bodies} - 8'd1)) >> 1;
                    if (num_steps == 32'd0) begin
                        done <= 1'b1;
                    end else begin
                        busy     <= 1'b1;
                        pi       <= 5'd0;
                        pj       <= 5'd1;
                        k        <= 7'd0;
                        received <= 8'd0;
                        state    <= S_FEED;
                    end
                end
            end

            // feed every pair into the pipeline, one per cycle
            S_FEED: begin
                pf_valid <= 1'b1;
                pf_tag   <= {1'b0, k};
                pf_xi <= bx[pi]; pf_yi <= by[pi]; pf_zi <= bz[pi]; pf_mi <= bm[pi];
                pf_xj <= bx[pj]; pf_yj <= by[pj]; pf_zj <= bz[pj]; pf_mj <= bm[pj];
                if (k == num_pairs - 7'd1) begin
                    state <= S_DRAIN;
                end else begin
                    k <= k + 7'd1;
                    if (pj == last_body_minus[4:0]) begin
                        pi <= pi + 5'd1;
                        pj <= pi + 5'd2;
                    end else begin
                        pj <= pj + 5'd1;
                    end
                end
            end

            // wait until all pair results are in the buffer
            S_DRAIN: begin
                if (received == {1'b0, num_pairs}) begin
                    pi    <= 5'd0;
                    pj    <= 5'd1;
                    k     <= 7'd0;
                    state <= S_ACC_GO;
                end
            end

            // apply pair k's deltas, in pair order
            S_ACC_GO: begin
                acc_valid <= 1'b1;
                acc_vix <= bvx[pi]; acc_viy <= bvy[pi]; acc_viz <= bvz[pi];
                acc_vjx <= bvx[pj]; acc_vjy <= bvy[pj]; acc_vjz <= bvz[pj];
                acc_dix <= r_ix[k]; acc_diy <= r_iy[k]; acc_diz <= r_iz[k];
                acc_djx <= r_jx[k]; acc_djy <= r_jy[k]; acc_djz <= r_jz[k];
                state <= S_ACC_WAIT;
            end

            S_ACC_WAIT: begin
                if (acc_ov[0]) begin
                    bvx[pi] <= acc_nix; bvy[pi] <= acc_niy; bvz[pi] <= acc_niz;
                    bvx[pj] <= acc_njx; bvy[pj] <= acc_njy; bvz[pj] <= acc_njz;
                    if (k == num_pairs - 7'd1) begin
                        pb    <= 5'd0;
                        state <= S_POS_MUL;
                    end else begin
                        k <= k + 7'd1;
                        if (pj == last_body_minus[4:0]) begin
                            pi <= pi + 5'd1;
                            pj <= pi + 5'd2;
                        end else begin
                            pj <= pj + 5'd1;
                        end
                        state <= S_ACC_GO;
                    end
                end
            end

            // position update of body pb: dt * v, then pos + dt * v
            S_POS_MUL: begin
                pm_valid <= 1'b1;
                pm_vx <= bvx[pb]; pm_vy <= bvy[pb]; pm_vz <= bvz[pb];
                state <= S_POS_MULW;
            end

            S_POS_MULW: begin
                if (pm_ov[0]) begin
                    pa_px <= pm_px; pa_py <= pm_py; pa_pz <= pm_pz;
                    state <= S_POS_ADD;
                end
            end

            S_POS_ADD: begin
                pa_valid <= 1'b1;
                pa_x <= bx[pb]; pa_y <= by[pb]; pa_z <= bz[pb];
                state <= S_POS_ADDW;
            end

            S_POS_ADDW: begin
                if (pa_ov[0]) begin
                    bx[pb] <= pa_nx; by[pb] <= pa_ny; bz[pb] <= pa_nz;
                    if (pb == last_body_minus[4:0]) begin
                        state <= S_STEP_END;
                    end else begin
                        pb    <= pb + 5'd1;
                        state <= S_POS_MUL;
                    end
                end
            end

            S_STEP_END: begin
                steps_done <= steps_done + 32'd1;
                if (steps_done + 32'd1 == num_steps) begin
                    busy  <= 1'b0;
                    done  <= 1'b1;
                    state <= S_IDLE;
                end else begin
                    pi       <= 5'd0;
                    pj       <= 5'd1;
                    k        <= 7'd0;
                    received <= 8'd0;
                    state    <= S_FEED;
                end
            end

            default: state <= S_IDLE;
            endcase
        end
    end

endmodule
