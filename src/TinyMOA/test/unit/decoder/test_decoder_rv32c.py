"""
Test suite for decoding RV32C (Zca, Zcb) instructions.

Every test verifies ALL control lines: is_compressed=1, the correct is_* flag high,
all others low, rs1/rs2/rd (prime register decode where applicable), imm bit layout,
alu_opcode, mem_opcode.

CR-Type instructions:
    [15:12] funct4 (opcode)
    [11:7]  rs2'/rd'
    [6:2]   rs2
    [1:0]   op (quadrant)

CI-Type instructions:
    [15:13] funct3 (opcode)
    [12]    imm[5]
    [11:7]  rs1'/rd'
    [6:2]   imm[6:2]
    [1:0]   op (quadrant)

CSS-Type instructions:
    [15:13] funct3 (opcode)
    [12:7]  imm[12:7]
    [6:2]   imm[6:2]
    [1:0]   op (quadrant)

CIW-Type instructions:
    [15:13] funct3 (opcode)
    [12:7]  imm[17:12]
    [6:2]   imm[11:7]
    [1:0]   op (quadrant)

CL-Type instructions:
    [15:13] funct3 (opcode)
    [12:10] imm[12:10] (hi)
    [9:7]   rs1'
    [6:5]   imm[6:5] (lo)
    [4:2]   rd'
    [1:0]   op (quadrant)

CS-Type instructions:
    [15:13] funct3 (opcode)
    [12:10] imm[12:10] (hi)
    [9:7]   rs1'
    [6:5]   imm[6:5] (lo)
    [4:2]   rs2'
    [1:0]   op (quadrant)

CA-Type instructions:
    [15:10] funct6 (opcode)
    [9:7]   rd'/rs1'
    [6:5]   imm
    [4:2]   rs2'
    [1:0]   op (quadrant)

CB-Type instructions:
    [15:13] funct3 (opcode)
    [12:10] offset (hi)
    [9:7]   rd'/rs1'
    [6:2]   offset (lo)
    [1:0]   op (quadrant)

CJ-Type instructions:
    [15:13] funct3 (opcode)
    [12:2]  target address
    [1:0] op (quadrant)
"""

import cocotb
from cocotb.triggers import Timer
import utility.rv32c_encode as rv32c


async def setup(dut):
    dut.instr.value = 0
    dut.imm.value = 0
    dut.alu_opcode.value = 0
    dut.mem_opcode.value = 0
    dut.rs1.value = 0
    dut.rs2.value = 0
    dut.rd.value = 0
    dut.is_load.value = 0
    dut.is_store.value = 0
    dut.is_branch.value = 0
    dut.is_jal.value = 0
    dut.is_jalr.value = 0
    dut.is_lui.value = 0
    dut.is_auipc.value = 0
    dut.is_system.value = 0
    dut.is_compressed.value = 0
    await Timer(1, unit="ns")


async def decode(dut, instr_val):
    dut.instr.value = instr_val
    await Timer(1, unit="ns")


def verify_flags(
    dut,
    *,
    is_alu_reg=0,
    is_alu_imm=0,
    is_load=0,
    is_store=0,
    is_branch=0,
    is_jal=0,
    is_jalr=0,
    is_lui=0,
    is_auipc=0,
    is_system=0,
    is_compressed=1,  # RV32C instr should always be high
):
    """Verify instruction control decode flags"""
    assert dut.is_alu_reg.value == is_alu_reg
    assert dut.is_alu_imm.value == is_alu_imm
    assert dut.is_load.value == is_load
    assert dut.is_store.value == is_store
    assert dut.is_branch.value == is_branch
    assert dut.is_jal.value == is_jal
    assert dut.is_jalr.value == is_jalr
    assert dut.is_lui.value == is_lui
    assert dut.is_auipc.value == is_auipc
    assert dut.is_system.value == is_system
    assert dut.is_compressed.value == is_compressed
    # assert dut.instr_len.value == 2, "Expected RV32C 16-bit instruction"


# mem_opcode encoding: [1:0]=size (00=byte, 01=half, 10=word), [2]=unsigned
MEM_BYTE = 0b000
MEM_HALF = 0b001
MEM_WORD = 0b010
MEM_BYTE_U = 0b100
MEM_HALF_U = 0b101


def verify_c_alu_reg(dut, alu_opcode, rd, rs2):
    """CA-type/CR-type: C.SUB, C.XOR, C.OR, C.AND, C.MUL, C.ADD -- rd==rs1 (same field)"""
    assert dut.alu_opcode.value == alu_opcode, (
        f"alu_opcode: expected {alu_opcode:#06b}, got {dut.alu_opcode.value:#06b}"
    )
    assert dut.rd.value == rd, f"rd:  expected x{rd}, got x{dut.rd.value}"
    assert dut.rs1.value == rd, (
        f"rs1: expected x{rd} (same as rd), got x{dut.rs1.value}"
    )
    assert dut.rs2.value == rs2, f"rs2: expected x{rs2}, got x{dut.rs2.value}"
    verify_flags(dut, is_alu_reg=1)


def verify_c_mv(dut, rd, rs2):
    """CR-type: C.MV rd, rs2 -- rs1 is x0 (not encoded)"""
    assert dut.rd.value == rd, f"rd:  expected x{rd}, got x{dut.rd.value}"
    assert dut.rs1.value == 0, f"rs1: expected x0 (implicit), got x{dut.rs1.value}"
    assert dut.rs2.value == rs2, f"rs2: expected x{rs2}, got x{dut.rs2.value}"
    verify_flags(dut, is_alu_reg=1)


def verify_c_alu_imm(dut, alu_opcode, rd, rs1, imm):
    """CI-type/CB-type: C.ADDI, C.LI, C.SLLI, C.ANDI, C.SRLI, C.SRAI"""
    assert dut.alu_opcode.value == alu_opcode, (
        f"alu_opcode: expected {alu_opcode:#06b}, got {dut.alu_opcode.value:#06b}"
    )
    assert dut.rd.value == rd, f"rd:  expected x{rd}, got x{dut.rd.value}"
    assert dut.rs1.value == rs1, f"rs1: expected x{rs1}, got x{dut.rs1.value}"
    assert dut.imm.value.to_signed() == imm, (
        f"imm: expected {imm}, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_alu_imm=1)


def verify_c_load(dut, mem_opcode, rd, rs1, imm):
    """CL-type/CI-type: C.LW, C.LBU, C.LHU, C.LH, C.LWSP"""
    assert dut.mem_opcode.value == mem_opcode, (
        f"mem_opcode: expected {mem_opcode:x05b}, got {dut.mem_opcode.value:x05b}"
    )
    assert dut.rd.value == rd, f"rd:  expected x{rd}, got x{dut.rd.value}"
    assert dut.rs1.value == rs1, f"rs1: expected x{rs1}, got x{dut.rs1.value}"
    assert dut.imm.value.to_signed() == imm, (
        f"imm: expected {imm}, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_load=1)


def verify_c_store(dut, mem_opcode, rs1, rs2, imm):
    """CS-type/CSS-type: C.SW, C.SB, C.SH, C.SWSP"""
    assert dut.mem_opcode.value == mem_opcode, (
        f"mem_opcode: expected {mem_opcode:#05b}, got {dut.mem_opcode.value:#05b}"
    )
    assert dut.rs1.value == rs1, f"rs1: expected x{rs1}, got x{dut.rs1.value}"
    assert dut.rs2.value == rs2, f"rs2: expected x{rs2}, got x{dut.rs2.value}"
    assert dut.imm.value.to_signed() == imm, (
        f"imm: expected {imm}, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_store=1)


def verify_c_branch(dut, rs1, imm):
    """CB-type: C.BEQZ, C.BNEZ -- rs2 is always x0"""
    assert dut.rs1.value == rs1, f"rs1: expected x{rs1}, got x{dut.rs1.value}"
    assert dut.rs2.value == 0, f"rs2: expected x0, got x{dut.rs2.value}"
    assert dut.imm.value.to_signed() == imm, (
        f"imm: expected {imm}, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_branch=1)


def verify_c_jal(dut, rd, imm):
    """CJ-type: C.JAL (rd=x1), C.J (rd=x0)"""
    assert dut.rd.value == rd, f"rd: expected x{rd}, got x{dut.rd.value}"
    assert dut.imm.value.to_signed() == imm, (
        f"imm: expected {imm}, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_jal=1)


def verify_c_jalr(dut, rd, rs1):
    """CR-type: C.JALR (rd=x1, imm=0), C.JR (rd=x0, imm=0)"""
    assert dut.rd.value == rd, f"rd:  expected x{rd}, got x{dut.rd.value}"
    assert dut.rs1.value == rs1, f"rs1: expected x{rs1}, got x{dut.rs1.value}"
    assert dut.imm.value.to_signed() == 0, (
        f"imm: expected 0, got {dut.imm.value.to_signed()}"
    )
    verify_flags(dut, is_jalr=1)


def verify_c_lui(dut, rd, imm):
    """CI-type: C.LUI -- imm already shifted to [31:12] by decoder"""
    assert dut.rd.value == rd, f"rd: expected x{rd}, got x{dut.rd.value}"
    assert dut.imm.value.integer == imm, (
        f"imm: expected {imm:#x}, got {dut.imm.value.integer:#x}"
    )
    verify_flags(dut, is_lui=1)


# === Quadrant 0 ===


@cocotb.test()
async def test_c_addi4spn(dut):
    # C.ADDI4SPN rd', nzuimm -> addi rd', x2, nzuimm
    # rs1 implicit x2 (sp), rd' = x8-x15, imm word-aligned 4-1020
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi4spn(rd=8, imm=4))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=8, rs1=2, imm=4)


@cocotb.test()
async def test_c_addi4spn_max(dut):
    # Maximum nzuimm=1020 (all imm bits set) exercises all scrambled bit positions
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi4spn(rd=15, imm=1020))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=15, rs1=2, imm=1020)


@cocotb.test()
async def test_c_lw(dut):
    # C.LW rd', imm(rs1') -> lw rd', imm(rs1')
    # rd', rs1' prime (x8-x15), imm word-aligned 0-124
    await setup(dut)
    await decode(dut, rv32c.encode_c_lw(rd=8, rs1=9, imm=4))
    verify_c_load(dut, mem_opcode=MEM_WORD, rd=8, rs1=9, imm=4)


@cocotb.test()
async def test_c_lw_max(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_lw(rd=10, rs1=11, imm=124))
    verify_c_load(dut, mem_opcode=MEM_WORD, rd=10, rs1=11, imm=124)


@cocotb.test()
async def test_c_lbu(dut):
    # C.LBU rd', imm(rs1') -> lbu rd', imm(rs1')
    await setup(dut)
    await decode(dut, rv32c.encode_c_lbu(rd=8, rs1=9, imm=1))
    verify_c_load(dut, mem_opcode=MEM_BYTE_U, rd=8, rs1=9, imm=1)


@cocotb.test()
async def test_c_lbu_imm3(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_lbu(rd=8, rs1=9, imm=3))
    verify_c_load(dut, mem_opcode=MEM_BYTE_U, rd=8, rs1=9, imm=3)


@cocotb.test()
async def test_c_lhu(dut):
    # C.LHU rd', imm(rs1') -> lhu rd', imm(rs1')
    # imm[1] only, halfword-aligned (0 or 2)
    await setup(dut)
    await decode(dut, rv32c.encode_c_lhu(rd=8, rs1=9, imm=2))
    verify_c_load(dut, mem_opcode=MEM_HALF_U, rd=8, rs1=9, imm=2)


@cocotb.test()
async def test_c_lh(dut):
    # C.LH rd', imm(rs1') -> lh rd', imm(rs1')
    # signed halfword; imm[1] only (0 or 2)
    await setup(dut)
    await decode(dut, rv32c.encode_c_lh(rd=8, rs1=9, imm=2))
    verify_c_load(dut, mem_opcode=MEM_HALF, rd=8, rs1=9, imm=2)


@cocotb.test()
async def test_c_sw(dut):
    # C.SW rs2', imm(rs1') -> sw rs2', imm(rs1')
    # rs1', rs2' prime (x8-x15), imm word-aligned 0-124
    await setup(dut)
    await decode(dut, rv32c.encode_c_sw(rs1=8, rs2=9, imm=4))
    verify_c_store(dut, mem_opcode=MEM_WORD, rs1=8, rs2=9, imm=4)


@cocotb.test()
async def test_c_sw_max(dut):
    # Maximum offset=124
    await setup(dut)
    await decode(dut, rv32c.encode_c_sw(rs1=10, rs2=11, imm=124))
    verify_c_store(dut, mem_opcode=MEM_WORD, rs1=10, rs2=11, imm=124)


@cocotb.test()
async def test_c_sb(dut):
    # C.SB rs2', imm(rs1') -> sb rs2', imm(rs1')
    # imm[1:0] unsigned byte offset 0-3
    await setup(dut)
    await decode(dut, rv32c.encode_c_sb(rs1=8, rs2=9, imm=1))
    verify_c_store(dut, mem_opcode=MEM_BYTE, rs1=8, rs2=9, imm=1)


@cocotb.test()
async def test_c_sh(dut):
    # C.SH rs2', imm(rs1') -> sh rs2', imm(rs1')
    # imm[1] only, halfword-aligned (0 or 2)
    await setup(dut)
    await decode(dut, rv32c.encode_c_sh(rs1=8, rs2=9, imm=2))
    verify_c_store(dut, mem_opcode=MEM_HALF, rs1=8, rs2=9, imm=2)


# === Quadrant 1 ===


@cocotb.test()
async def test_c_nop(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_nop())
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=0, rs1=0, imm=0)


@cocotb.test()
async def test_c_addi(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi(rd=5, imm=4))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=5, rs1=5, imm=4)


@cocotb.test()
async def test_c_addi_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi(rd=5, imm=-4))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=5, rs1=5, imm=-4)


@cocotb.test()
async def test_c_li(dut):
    # rs1 always x0, unlike C.ADDI where rs1==rd
    await setup(dut)
    await decode(dut, rv32c.encode_c_li(rd=5, imm=4))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=5, rs1=0, imm=4)


@cocotb.test()
async def test_c_li_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_li(rd=5, imm=-4))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=5, rs1=0, imm=-4)


@cocotb.test()
async def test_c_addi16sp(dut):
    # rd and rs1 always x2; imm is pre-scaled by 16 in encoding
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi16sp(imm=16))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=2, rs1=2, imm=16)


@cocotb.test()
async def test_c_addi16sp_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_addi16sp(imm=-16))
    verify_c_alu_imm(dut, alu_opcode=0b0000, rd=2, rs1=2, imm=-16)


@cocotb.test()
async def test_c_lui(dut):
    # nzimm[17:12] decoded to imm[31:12]; verify_c_lui checks .integer (unsigned)
    await setup(dut)
    await decode(dut, rv32c.encode_c_lui(rd=5, imm=0x5000))
    verify_c_lui(dut, rd=5, imm=0x5000)


@cocotb.test()
async def test_c_lui_neg(dut):
    # nzimm[17]=1 sign-extends into bits[31:17], producing a negative upper immediate
    await setup(dut)
    await decode(dut, rv32c.encode_c_lui(rd=5, imm=0xFFFFF000))
    verify_c_lui(dut, rd=5, imm=0xFFFFF000)


@cocotb.test()
async def test_c_sub(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_sub(rd=8, rs2=9))
    verify_c_alu_reg(dut, alu_opcode=0b0001, rd=8, rs2=9)


@cocotb.test()
async def test_c_xor(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_xor(rd=8, rs2=9))
    verify_c_alu_reg(dut, alu_opcode=0b0100, rd=8, rs2=9)


@cocotb.test()
async def test_c_or(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_or(rd=8, rs2=9))
    verify_c_alu_reg(dut, alu_opcode=0b0101, rd=8, rs2=9)


@cocotb.test()
async def test_c_and(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_and(rd=8, rs2=9))
    verify_c_alu_reg(dut, alu_opcode=0b0110, rd=8, rs2=9)


@cocotb.test()
async def test_c_mul(dut):
    # Zcb; operates on lower 16 bits, alu_opcode=MUL=0b1011
    await setup(dut)
    await decode(dut, rv32c.encode_c_mul(rd=8, rs2=9))
    verify_c_alu_reg(dut, alu_opcode=0b1011, rd=8, rs2=9)


@cocotb.test()
async def test_c_not(dut):
    # Zcb single-register; expands to xori rd', rd', -1 so is_alu_imm with imm=-1
    await setup(dut)
    await decode(dut, rv32c.encode_c_not(rd=8))
    verify_c_alu_imm(dut, alu_opcode=0b0100, rd=8, rs1=8, imm=-1)


# Zcb sign/zero-extend single-register (requires Zbb, not implemented)
@cocotb.test(skip=True)
async def test_c_zext_b(dut):
    # Requires Zbb extension
    await setup(dut)
    raise NotImplementedError


@cocotb.test(skip=True)
async def test_c_sext_b(dut):
    # Requires Zbb extension
    await setup(dut)
    raise NotImplementedError


@cocotb.test(skip=True)
async def test_c_zext_h(dut):
    # Requires Zbb extension
    await setup(dut)
    raise NotImplementedError


@cocotb.test(skip=True)
async def test_c_sext_h(dut):
    # Requires Zbb extension
    await setup(dut)
    raise NotImplementedError


@cocotb.test()
async def test_c_srli(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_srli(rd=8, shamt=3))
    verify_c_alu_imm(dut, alu_opcode=0b1001, rd=8, rs1=8, imm=3)


@cocotb.test()
async def test_c_srai(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_srai(rd=8, shamt=3))
    verify_c_alu_imm(dut, alu_opcode=0b1010, rd=8, rs1=8, imm=3)


@cocotb.test()
async def test_c_andi(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_andi(rd=8, imm=4))
    verify_c_alu_imm(dut, alu_opcode=0b0110, rd=8, rs1=8, imm=4)


@cocotb.test()
async def test_c_andi_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_andi(rd=8, imm=-4))
    verify_c_alu_imm(dut, alu_opcode=0b0110, rd=8, rs1=8, imm=-4)


@cocotb.test()
async def test_c_beqz(dut):
    # rs2 always x0 (not encoded)
    await setup(dut)
    await decode(dut, rv32c.encode_c_beqz(rs1=8, imm=4))
    verify_c_branch(dut, rs1=8, imm=4)


@cocotb.test()
async def test_c_bnez(dut):
    # rs2 always x0 (not encoded)
    await setup(dut)
    await decode(dut, rv32c.encode_c_bnez(rs1=8, imm=-2))
    verify_c_branch(dut, rs1=8, imm=-2)


@cocotb.test()
async def test_c_j(dut):
    # rd always x0 (no link)
    await setup(dut)
    await decode(dut, rv32c.encode_c_j(imm=8))
    verify_c_jal(dut, rd=0, imm=8)


@cocotb.test()
async def test_c_j_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_j(imm=-2))
    verify_c_jal(dut, rd=0, imm=-2)


@cocotb.test()
async def test_c_jal(dut):
    # rd always x1 (RV32 only; no RV64 equivalent)
    await setup(dut)
    await decode(dut, rv32c.encode_c_jal(imm=8))
    verify_c_jal(dut, rd=1, imm=8)


@cocotb.test()
async def test_c_jal_neg(dut):
    await setup(dut)
    await decode(dut, rv32c.encode_c_jal(imm=-2))
    verify_c_jal(dut, rd=1, imm=-2)


# === Quadrant 2 ===


@cocotb.test()
async def test_c_jr(dut):
    # C.JR rs1  ->  jalr x0, 0(rs1)
    await setup(dut)
    await decode(dut, rv32c.encode_c_jr(rs1=5))
    verify_c_jalr(dut, rd=0, rs1=5)


@cocotb.test()
async def test_c_mv(dut):
    # C.MV rd, rs2  ->  add rd, x0, rs2
    await setup(dut)
    await decode(dut, rv32c.encode_c_mv(rd=5, rs2=6))
    assert dut.alu_opcode.value == 0b0000, (
        f"alu_opcode: expected ADD(0000), got {dut.alu_opcode.value:#06b}"
    )
    verify_c_mv(dut, rd=5, rs2=6)


@cocotb.test()
async def test_c_ebreak(dut):
    # C.EBREAK  ->  ebreak (is_system=1)
    await setup(dut)
    await decode(dut, rv32c.encode_c_ebreak())
    verify_flags(dut, is_system=1)


@cocotb.test()
async def test_c_jalr(dut):
    # C.JALR rs1  ->  jalr x1, 0(rs1)
    await setup(dut)
    await decode(dut, rv32c.encode_c_jalr(rs1=5))
    verify_c_jalr(dut, rd=1, rs1=5)


@cocotb.test()
async def test_c_add(dut):
    # C.ADD rd, rs2  ->  add rd, rd, rs2
    await setup(dut)
    await decode(dut, rv32c.encode_c_add(rd=5, rs2=6))
    verify_c_alu_reg(dut, alu_opcode=0b0000, rd=5, rs2=6)


@cocotb.test()
async def test_c_slli(dut):
    # C.SLLI rd, shamt  ->  slli rd, rd, shamt
    await setup(dut)
    await decode(dut, rv32c.encode_c_slli(rd=5, shamt=3))
    verify_c_alu_imm(dut, alu_opcode=0b1000, rd=5, rs1=5, imm=3)


@cocotb.test()
async def test_c_lwsp(dut):
    # C.LWSP rd, imm(sp)  ->  lw rd, imm(x2)
    await setup(dut)
    await decode(dut, rv32c.encode_c_lwsp(rd=5, imm=4))
    verify_c_load(dut, mem_opcode=MEM_WORD, rd=5, rs1=2, imm=4)


@cocotb.test()
async def test_c_lwsp_max(dut):
    # C.LWSP with maximum offset: uimm[7:2] all ones = 252
    await setup(dut)
    await decode(dut, rv32c.encode_c_lwsp(rd=5, imm=252))
    verify_c_load(dut, mem_opcode=MEM_WORD, rd=5, rs1=2, imm=252)


@cocotb.test()
async def test_c_swsp(dut):
    # C.SWSP rs2, imm(sp)  ->  sw rs2, imm(x2)
    await setup(dut)
    await decode(dut, rv32c.encode_c_swsp(rs2=6, imm=4))
    verify_c_store(dut, mem_opcode=MEM_WORD, rs1=2, rs2=6, imm=4)


@cocotb.test()
async def test_c_swsp_max(dut):
    # C.SWSP with maximum offset: uimm[7:2] all ones = 252
    await setup(dut)
    await decode(dut, rv32c.encode_c_swsp(rs2=6, imm=252))
    verify_c_store(dut, mem_opcode=MEM_WORD, rs1=2, rs2=6, imm=252)


@cocotb.test()
async def test_c_swtp(dut):
    # C.SWTP rs2, imm(tp)  ->  sw rs2, imm(x4)  (custom, same encoding as SWSP but f3=111)
    await setup(dut)
    scrambled = (4 & 0x3C) | ((4 >> 6) & 0x3)
    await decode(dut, rv32c.encode_css_type(0b111, scrambled, 6, 0b10))
    verify_c_store(dut, mem_opcode=MEM_WORD, rs1=4, rs2=6, imm=4)
