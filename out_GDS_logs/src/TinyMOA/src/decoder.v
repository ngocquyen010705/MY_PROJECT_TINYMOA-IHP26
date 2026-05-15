// TinyMOA Combinational Instruction Decoder
//
// Decodes RV32I, C/Zca, Zcb, and Zicond from a 32-bit word.
// 16-bit compressed instructions arrive zero-extended to 32 bits.
//
// Compressed register fields (3-bit) map to x8-x15: rd = {1'b1, instr[N:M]}.

`default_nettype none
`timescale 1ns / 1ps

module tinymoa_decoder (
    input [31:0] instr,

    output reg  [31:0] imm,
    output reg  [3:0]  alu_opcode,
    output reg  [2:0]  mem_opcode, // [1:0]=size, [2]=unsigned
    output reg  [3:0]  rs1,
    output reg  [3:0]  rs2,
    output reg  [3:0]  rd,

    output reg         is_load,
    output reg         is_store,
    output reg         is_branch,
    output reg         is_jal,
    output reg         is_jalr,
    output reg         is_lui,
    output reg         is_auipc,
    output reg         is_alu_reg,
    output reg         is_alu_imm,
    output reg         is_system,
    output reg         is_compressed
);

    // Hardcoded bit-fields to prevent slicing mistakes.

    // R-Type instructions:
    // [31:25] funct7
    // [24:20] rs2
    // [19:15] rs1
    // [14:12] funct3
    // [11:7]  rd
    // [6:0]   opcode

    // I-Type instructions:
    // [31:20] imm[11:0]
    // [19:15] rs1
    // [14:12] funct3
    // [11:7]  rd
    // [6:0]   opcode

    // S-Type instructions:
    // [31:25] imm[11:5]
    // [24:20] rs2
    // [19:15] rs1
    // [14:12] funct3
    // [11:7]  imm[4:0]
    // [6:0]   opcode

    // B-Type instructions:
    // [31]    imm[12]
    // [30:25] imm[10:5]
    // [24:20] rs2
    // [19:15] rs1
    // [14:12] funct3
    // [11:8]  imm[4:1]
    // [7]     imm[11]
    // [6:0]   opcode

    // U-Type instructions:
    // [31:12] imm[31:12]
    // [11:7]  rd
    // [6:0]   opcode

    // J-Type instructions:
    // [31]    imm[20]
    // [30:21] imm[10:1]
    // [20]    imm[11]
    // [19:12] imm[19:12]
    // [11:7]  rd
    // [6:0]   opcode

    // RV32C Compressed ISA

    // CR-Type instructions:
    // [15:12] funct4 (opcode)
    // [11:7]  rs2'/rd'
    // [6:2]   rs2
    // [1:0]   op (quadrant)

    // CI-Type instructions:
    // [15:13] funct3 (opcode)
    // [12]    imm[5]
    // [11:7]  rs1'/rd'
    // [6:2]   imm[6:2]
    // [1:0]   op (quadrant)

    // CSS-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:7]  imm[12:7]
    // [6:2]   imm[6:2]
    // [1:0]   op (quadrant)

    // CIW-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:7]  imm[17:12]
    // [6:2]   imm[11:7]
    // [1:0]   op (quadrant)
    
    // CL-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:10] imm[12:10] (hi)
    // [9:7]   rs1'
    // [6:5]   imm[6:5] (lo)
    // [4:2]   rd'
    // [1:0]   op (quadrant)

    // CS-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:10] imm[12:10] (hi)
    // [9:7]   rs1'
    // [6:5]   imm[6:5] (lo)
    // [4:2]   rs2'
    // [1:0]   op (quadrant)

    // CA-Type instructions:
    // [15:10] funct6 (opcode)
    // [9:7]   rd'/rs1'
    // [6:5]   imm
    // [4:2]   rs2'
    // [1:0]   op (quadrant)

    // CB-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:10] offset (hi)
    // [9:7]   rd'/rs1'
    // [6:2]   offset (lo)
    // [1:0]   op (quadrant)

    // CJ-Type instructions:
    // [15:13] funct3 (opcode)
    // [12:2]  target address
    // [1:0]   op (quadrant)

    wire [1:0] quadrant = instr[1:0];
    wire [4:0] i_opcode = instr[6:2];   // bits[1:0] == 2'b11 for all 32-bit instructions
    wire [2:0] c_funct3 = instr[15:13]; // compressed major opcode

    wire [2:0] funct3   = instr[14:12];
    wire [6:0] funct7   = instr[31:25];

    // 32-bit register fields (RV32E: 4-bit, x0-x15)
    wire [3:0] rs1_32 = instr[18:15];
    wire [3:0] rs2_32 = instr[23:20];
    wire [3:0] rd_32  = instr[10:7];

    // Compressed prime register fields: 3-bit encoding maps to x8-x15 ({1'b1, field})
    wire [3:0] c_rs1p = {1'b1, instr[9:7]};
    wire [3:0] c_rs2p = {1'b1, instr[4:2]};
    wire [3:0] c_rdp  = {1'b1, instr[4:2]};

    // Compressed full register fields (non-prime, used in CI/CR/CSS types)
    wire [3:0] c_rs1 = instr[10:7];
    wire [3:0] c_rs2 = instr[5:2];  // instr[6] always 0 for RV32E (x0-x15 only)
    wire [3:0] c_rd  = instr[10:7];

    always @(*) begin
        imm           = 32'b0;
        alu_opcode    = 4'b0;
        mem_opcode    = 3'b0;
        rs1           = 4'b0;
        rs2           = 4'b0;
        rd            = 4'b0;
        is_load       = 1'b0;
        is_store      = 1'b0;
        is_branch     = 1'b0;
        is_jal        = 1'b0;
        is_jalr       = 1'b0;
        is_lui        = 1'b0;
        is_auipc      = 1'b0;
        is_alu_reg    = 1'b0;
        is_alu_imm    = 1'b0;
        is_system     = 1'b0;
        is_compressed = 1'b0;

        // === RV32I 32-bit instructions ===
        if (quadrant == 2'b11) begin
            rs1 = rs1_32;
            rs2 = rs2_32;
            rd  = rd_32;

            case (i_opcode)

                // === R-Type: Register-register and Zicond ===
                5'b01100: begin
                    is_alu_reg = 1'b1;

                    // Zicond: funct7=0000111, funct3=101 (EQZ) or 110 (NEZ)
                    if (funct7 == 7'b0000111) begin
                        alu_opcode = {3'b111, funct3[1]}; // CZERO.EQZ=1110, CZERO.NEZ=1111

                    // Standard ALU operations
                    end else begin
                        case (funct3)
                            3'b000: alu_opcode = funct7[5] ? 4'b0001 : 4'b0000; // SUB : ADD
                            3'b001: alu_opcode = 4'b1000;                       // SLL
                            3'b010: alu_opcode = 4'b0010;                       // SLT
                            3'b011: alu_opcode = 4'b0011;                       // SLTU
                            3'b100: alu_opcode = 4'b0100;                       // XOR
                            3'b101: alu_opcode = funct7[5] ? 4'b1010 : 4'b1001; // SRA : SRL
                            3'b110: alu_opcode = 4'b0101;                       // OR
                            3'b111: alu_opcode = 4'b0110;                       // AND
                        endcase
                    end
                end

                // === I-Type: ALU immediate ===
                // imm[11:0] = instr[31:20], sign-extended
                // Shifts: shamt = imm[4:0] = instr[24:20], SRAI/SRLI via instr[30]
                5'b00100: begin
                    is_alu_imm = 1'b1;
                    imm = {{20{instr[31]}}, instr[31:20]};
                    case (funct3)
                        3'b000: alu_opcode = 4'b0000;                       // ADDI
                        3'b001: alu_opcode = 4'b1000;                       // SLLI
                        3'b010: alu_opcode = 4'b0010;                       // SLTI
                        3'b011: alu_opcode = 4'b0011;                       // SLTIU
                        3'b100: alu_opcode = 4'b0100;                       // XORI
                        3'b101: alu_opcode = instr[30] ? 4'b1010 : 4'b1001; // SRAI : SRLI
                        3'b110: alu_opcode = 4'b0101;                       // ORI
                        3'b111: alu_opcode = 4'b0110;                       // ANDI
                    endcase
                end

                // === I-Type: Load ===
                // imm[11:0] = instr[31:20], sign-extended
                // funct3: LB=000, LH=001, LW=010, LBU=100, LHU=101
                // mem_opcode[1:0]=size (00=byte,01=half,10=word), [2]=unsigned
                5'b00000: begin
                    is_load    = 1'b1;
                    imm        = {{20{instr[31]}}, instr[31:20]};
                    mem_opcode = {funct3[2], funct3[1:0]};
                end

                // === I-Type: JALR ===
                // funct3=000, target = (rs1 + sign-ext imm) & ~1
                5'b11001: begin
                    is_jalr = 1'b1;
                    imm     = {{20{instr[31]}}, instr[31:20]};
                end

                // === S-Type instructions ===
                // imm[11:5] = instr[31:25], imm[4:0] = instr[11:7]
                // funct3: SB=000, SH=001, SW=010
                5'b01000: begin
                    is_store   = 1'b1;
                    imm        = {{20{instr[31]}}, instr[31:25], instr[11:7]};
                    mem_opcode = {1'b0, funct3[1:0]};
                end

                // === B-Type instructions ===
                // imm[12|10:5] = instr[31:25], imm[4:1|11] = instr[11:7]
                // funct3: BEQ=000, BNE=001, BLT=100, BGE=101, BLTU=110, BGEU=111
                5'b11000: begin
                    is_branch = 1'b1;
                    imm       = {{19{instr[31]}}, instr[31], instr[7], instr[30:25], instr[11:8], 1'b0};
                    case (funct3)
                        3'b000, 3'b001: alu_opcode = 4'b0001; // BEQ/BNE -> SUB
                        3'b100, 3'b101: alu_opcode = 4'b0010; // BLT/BGE -> SLT
                        3'b110, 3'b111: alu_opcode = 4'b0011; // BLTU/BGEU -> SLTU
                        default:        alu_opcode = 4'b0001;
                    endcase
                end

                // === U-Type: AUIPC ===
                // imm[31:12] = instr[31:12], imm[11:0] = 0
                5'b00101: begin
                    is_auipc = 1'b1;
                    imm      = {instr[31:12], 12'b0};
                end

                // === U-Type: LUI ===
                // imm[31:12] = instr[31:12], imm[11:0] = 0
                5'b01101: begin
                    is_lui = 1'b1;
                    imm    = {instr[31:12], 12'b0};
                end

                // === J-Type: JAL ===
                // imm[20|10:1|11|19:12] scrambled across instr[31:12]
                5'b11011: begin
                    is_jal = 1'b1;
                    imm    = {{11{instr[31]}}, instr[31], instr[19:12], instr[20], instr[30:21], 1'b0};
                end

                // === SYSTEM instructions ===
                5'b11100: begin
                    is_system = 1'b1;
                end

                // FENCE: NOP
                5'b00011: begin end
            endcase

        // === RV32C 16-bit compressed instructions ===
        end else begin
            is_compressed = 1'b1;

            case (quadrant)

                // === Quadrant 0 ===
                // f3=000  C.ADDI4SPN  CIW  rd'=c_rdp,   rs1=x2,      imm[9:2]
                // f3=010  C.LW        CL   rd'=c_rdp,   rs1'=c_rs1p, imm[6:2]
                // f3=100  C.LBU       Zcb  rd'=c_rdp,   rs1'=c_rs1p, imm[1:0]
                // f3=100  C.LHU       Zcb  rd'=c_rdp,   rs1'=c_rs1p, imm[1]
                // f3=100  C.LH        Zcb  rd'=c_rdp,   rs1'=c_rs1p, imm[1]
                // f3=100  C.SB        Zcb  rs1'=c_rs1p, rs2'=c_rs2p, imm[1:0]
                // f3=100  C.SH        Zcb  rs1'=c_rs1p, rs2'=c_rs2p, imm[1]
                // f3=110  C.SW        CS   rs1'=c_rs1p, rs2'=c_rs2p, imm[6:2]
                2'b00: begin
                    case (c_funct3)
                        3'b000: begin // C.ADDI4SPN
                            is_alu_imm = 1'b1;
                            alu_opcode = 4'b0000;
                            rs1        = 4'd2; // x2 (sp)
                            rd         = c_rdp;
                            imm        = {22'b0, instr[10:7], instr[12:11], instr[5], instr[6], 2'b00};
                        end
                        3'b010: begin // C.LW
                            is_load    = 1'b1;
                            mem_opcode = 3'b010;
                            rs1        = c_rs1p;
                            rd         = c_rdp;
                            imm        = {25'b0, instr[5], instr[12:10], instr[6], 2'b00};
                        end
                        3'b100: begin
                            case (instr[11:10])
                                2'b00: begin // C.LBU
                                    is_load    = 1'b1;
                                    mem_opcode = 3'b100;
                                    rs1        = c_rs1p;
                                    rd         = c_rdp;
                                    imm        = {30'b0, instr[5], instr[6]};
                                end
                                2'b01: begin
                                    if (instr[6]) begin // C.LH (signed)
                                        is_load    = 1'b1;
                                        mem_opcode = 3'b001;
                                        rs1        = c_rs1p;
                                        rd         = c_rdp;
                                        imm        = {30'b0, instr[5], 1'b0};
                                    end else begin // C.LHU (unsigned)
                                        is_load    = 1'b1;
                                        mem_opcode = 3'b101;
                                        rs1        = c_rs1p;
                                        rd         = c_rdp;
                                        imm        = {30'b0, instr[5], 1'b0};
                                    end
                                end
                                2'b10: begin // C.SB
                                    is_store   = 1'b1;
                                    mem_opcode = 3'b000;
                                    rs1        = c_rs1p;
                                    rs2        = c_rs2p;
                                    imm        = {30'b0, instr[5], instr[6]};
                                end
                                2'b11: begin // C.SH
                                    is_store   = 1'b1;
                                    mem_opcode = 3'b001;
                                    rs1        = c_rs1p;
                                    rs2        = c_rs2p;
                                    imm        = {30'b0, instr[5], 1'b0};
                                end
                            endcase
                        end
                        3'b110: begin // C.SW
                            is_store   = 1'b1;
                            mem_opcode = 3'b010;
                            rs1        = c_rs1p;
                            rs2        = c_rs2p;
                            imm        = {25'b0, instr[5], instr[12:10], instr[6], 2'b00};
                        end
                    endcase
                end

                // === Quadrant 1 ===
                // f3=000  C.NOP       CI   (rd=x0, imm=0)
                // f3=000  C.ADDI      CI   rd=c_rd,    rs1=c_rd, imm[5:0]   sign-ext          (rd!=0, imm!=0)
                // f3=001  C.JAL       CJ   rd=x1,      imm[11:1]            (scrambled)
                // f3=010  C.LI        CI   rd=c_rd,    rs1=x0,   imm[5:0]   sign-ext
                // f3=011  C.ADDI16SP  CI   rd=x2,      rs1=x2,   nzimm[9:4] scaled*16         (rd==2)
                // f3=011  C.LUI       CI   rd=c_rd,              nzimm[17:12] -> {imm,12'b0}  (rd!=0,2)
                // f3=100  C.SRLI      CB   rd'=c_rs1p, shamt[5:0]           (instr[11:10]=00)
                // f3=100  C.SRAI      CB   rd'=c_rs1p, shamt[5:0]           (instr[11:10]=01)
                // f3=100  C.ANDI      CB   rd'=c_rs1p, imm[5:0] sign-ext    (instr[11:10]=10)
                // f3=100  C.SUB       CA   rd'=c_rs1p, rs2'=c_rs2p          (instr[11:10]=11, instr[12]=0, instr[6:5]=00)
                // f3=100  C.XOR       CA   rd'=c_rs1p, rs2'=c_rs2p          (instr[11:10]=11, instr[12]=0, instr[6:5]=01)
                // f3=100  C.OR        CA   rd'=c_rs1p, rs2'=c_rs2p          (instr[11:10]=11, instr[12]=0, instr[6:5]=10)
                // f3=100  C.AND       CA   rd'=c_rs1p, rs2'=c_rs2p          (instr[11:10]=11, instr[12]=0, instr[6:5]=11)
                // f3=100  C.MUL       Zcb  rd'=c_rs1p, rs2'=c_rs2p          (instr[11:10]=11, instr[12]=1, instr[6:5]=10)
                // f3=100  C.NOT       Zcb  rd'=c_rs1p                       (instr[11:10]=11, instr[12]=1, instr[6:5]=00)
                // f3=101  C.J         CJ   rd=x0,      imm[11:1]            (scrambled)
                // f3=110  C.BEQZ      CB   rs1'=c_rs1p, rs2=x0,   imm[8:1]  (scrambled)
                // f3=111  C.BNEZ      CB   rs1'=c_rs1p, rs2=x0,   imm[8:1]  (scrambled)
                2'b01: begin
                    case (c_funct3)
                        3'b000: begin // C.NOP / C.ADDI
                            is_alu_imm = 1'b1;
                            alu_opcode = 4'b0000;
                            rd         = c_rd;
                            rs1        = c_rd;
                            imm        = {{26{instr[12]}}, instr[12], instr[6:2]};
                        end
                        3'b001: begin // C.JAL
                            is_jal = 1'b1;
                            rd     = 4'd1;
                            imm    = {{21{instr[12]}}, instr[8], instr[10:9], instr[6], instr[7], instr[2], instr[11], instr[5:3], 1'b0};
                        end
                        3'b010: begin // C.LI
                            is_alu_imm = 1'b1;
                            alu_opcode = 4'b0000;
                            rd         = c_rd;
                            rs1        = 4'd0;
                            imm        = {{26{instr[12]}}, instr[12], instr[6:2]};
                        end
                        3'b011: begin // C.ADDI16SP (rd==2) / C.LUI (rd!=2)
                            if (c_rd == 4'd2) begin // C.ADDI16SP
                                is_alu_imm = 1'b1;
                                alu_opcode = 4'b0000;
                                rd         = 4'd2;
                                rs1        = 4'd2;
                                imm        = {{23{instr[12]}}, instr[4:3], instr[5], instr[2], instr[6], 4'b0};
                            end else begin           // C.LUI
                                is_lui = 1'b1;
                                rd     = c_rd;
                                imm    = {{14{instr[12]}}, instr[12], instr[6:2], 12'b0};
                            end
                        end
                        3'b100: begin
                            case (instr[11:10])
                                2'b00: begin // C.SRLI
                                    is_alu_imm = 1'b1;
                                    alu_opcode = 4'b1001;
                                    rd         = c_rs1p;
                                    rs1        = c_rs1p;
                                    imm        = {26'b0, instr[12], instr[6:2]};
                                end
                                2'b01: begin // C.SRAI
                                    is_alu_imm = 1'b1;
                                    alu_opcode = 4'b1010;
                                    rd         = c_rs1p;
                                    rs1        = c_rs1p;
                                    imm        = {26'b0, instr[12], instr[6:2]};
                                end
                                2'b10: begin // C.ANDI
                                    is_alu_imm = 1'b1;
                                    alu_opcode = 4'b0110;
                                    rd         = c_rs1p;
                                    rs1        = c_rs1p;
                                    imm        = {{26{instr[12]}}, instr[12], instr[6:2]};
                                end
                                2'b11: begin
                                    case ({instr[12], instr[6:5]})
                                        3'b000: begin // C.SUB
                                            is_alu_reg = 1'b1;
                                            alu_opcode = 4'b0001;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            rs2        = c_rs2p;
                                        end
                                        3'b001: begin // C.XOR
                                            is_alu_reg = 1'b1;
                                            alu_opcode = 4'b0100;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            rs2        = c_rs2p;
                                        end
                                        3'b010: begin // C.OR
                                            is_alu_reg = 1'b1;
                                            alu_opcode = 4'b0101;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            rs2        = c_rs2p;
                                        end
                                        3'b011: begin // C.AND
                                            is_alu_reg = 1'b1;
                                            alu_opcode = 4'b0110;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            rs2        = c_rs2p;
                                        end
                                        3'b110: begin // C.MUL (Zcb)
                                            is_alu_reg = 1'b1;
                                            alu_opcode = 4'b1011;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            rs2        = c_rs2p;
                                        end
                                        3'b100: begin // C.NOT (Zcb)
                                            is_alu_imm = 1'b1;
                                            alu_opcode = 4'b0100;
                                            rd         = c_rs1p;
                                            rs1        = c_rs1p;
                                            imm        = 32'hFFFFFFFF;
                                        end
                                    endcase
                                end
                            endcase
                        end
                        3'b101: begin // C.J
                            is_jal = 1'b1;
                            rd     = 4'd0;
                            imm    = {{21{instr[12]}}, instr[8], instr[10:9], instr[6], instr[7], instr[2], instr[11], instr[5:3], 1'b0};
                        end
                        3'b110: begin // C.BEQZ
                            is_branch  = 1'b1;
                            alu_opcode = 4'b0001;
                            rs1        = c_rs1p;
                            rs2        = 4'd0;
                            imm        = {{24{instr[12]}}, instr[6:5], instr[2], instr[11:10], instr[4:3], 1'b0};
                        end
                        3'b111: begin // C.BNEZ
                            is_branch  = 1'b1;
                            alu_opcode = 4'b0001;
                            rs1        = c_rs1p;
                            rs2        = 4'd0;
                            imm        = {{24{instr[12]}}, instr[6:5], instr[2], instr[11:10], instr[4:3], 1'b0};
                        end
                    endcase
                end

                // === Quadrant 2 ===
                // f3=000  C.SLLI      CI   rd=c_rd,   rs1=c_rd,  shamt[5:0]
                // f3=010  C.LWSP      CI   rd=c_rd,   rs1=x2,    uimm[7:2]
                // f3=100  C.JR        CR   rs1=c_rs1, rd=x0,     imm=0      ({instr[12],rs2==0}=2'b01)
                // f3=100  C.MV        CR   rd=c_rd,   rs1=x0,    rs2=c_rs2  ({instr[12],rs2==0}=2'b00)
                // f3=100  C.EBREAK    CR   is_system                        ({instr[12],rs2==0}=2'b11, rs1==0)
                // f3=100  C.JALR      CR   rd=x1,     rs1=c_rs1, imm=0      ({instr[12],rs2==0}=2'b11, rs1!=0)
                // f3=100  C.ADD       CR   rd=c_rd,   rs1=c_rd,  rs2=c_rs2  ({instr[12],rs2==0}=2'b10)
                // f3=110  C.SWSP      CSS  rs1=x2,    rs2=c_rs2, uimm[7:2]
                // f3=111  C.SWTP      CSS  rs1=x4,    rs2=c_rs2, uimm[7:2]  (custom)
                2'b10: begin
                    case (c_funct3)
                        3'b000: begin // C.SLLI
                            is_alu_imm = 1'b1;
                            alu_opcode = 4'b1000;
                            rd         = c_rd;
                            rs1        = c_rs1;
                            imm        = {26'b0, instr[12], instr[6:2]};
                        end
                        3'b010: begin // C.LWSP
                            is_load    = 1'b1;
                            mem_opcode = 3'b010; // word
                            rs1        = 4'd2;   // x2 (sp)
                            rd         = c_rd;
                            imm        = {24'b0, instr[3:2], instr[12], instr[6:4], 2'b00};
                        end
                        3'b100: begin
                            case ({instr[12], c_rs2 == 4'd0})
                                2'b00: begin // C.MV
                                    is_alu_reg = 1'b1;
                                    alu_opcode = 4'b0000;
                                    rs1        = 4'd0; // x0
                                    rs2        = c_rs2;
                                    rd         = c_rd;
                                end
                                2'b01: begin // C.JR
                                    is_jalr = 1'b1;
                                    rd      = 4'd0;
                                    rs1     = c_rs1;
                                    imm     = 32'b0;
                                end
                                2'b10: begin // C.ADD
                                    is_alu_reg = 1'b1;
                                    alu_opcode = 4'b0000;
                                    rd         = c_rd;
                                    rs1        = c_rs1;
                                    rs2        = c_rs2;
                                end
                                2'b11: begin
                                    if (c_rs1 == 4'd0) begin // C.EBREAK
                                        is_system = 1'b1;
                                    end else begin           // C.JALR
                                        is_jalr = 1'b1;
                                        rs1     = c_rs1;
                                        imm     = 32'b0;
                                        rd      = 4'd1;      // x1 (link)
                                    end
                                end
                            endcase
                        end
                        3'b110: begin // C.SWSP
                            is_store   = 1'b1;
                            mem_opcode = 3'b010;
                            rs1        = 4'd2; // x2 (sp)
                            rs2        = c_rs2;
                            imm        = {24'b0, instr[8:7], instr[12:9], 2'b00};
                        end
                        3'b111: begin // C.SWTP (custom store word to tp-relative)
                            is_store   = 1'b1;
                            mem_opcode = 3'b010;
                            rs1        = 4'd4; // x4 (tp)
                            rs2        = c_rs2;
                            imm        = {24'b0, instr[8:7], instr[12:9], 2'b00};
                        end
                    endcase
                end
            endcase
        end
    end
endmodule
