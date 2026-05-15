"""
Test suite for TCM (sram_wrapper, behavioral model)

- write_all_zeros
- write_all_ones
- write_read
- cross_write_read
- concurrent_write_same_address
- write_alternating_pattern
- address_boundary_zero
- address_boundary_max
- multiple_sequential_writes_then_reads
- back_to_back_reads
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


async def setup(dut):
    """Initialize the TCM block (no nrst on DUT)."""
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.a_en.value = 0
    dut.a_wen.value = 0
    dut.a_addr.value = 0
    dut.a_din.value = 0
    dut.b_en.value = 0
    dut.b_wen.value = 0
    dut.b_addr.value = 0
    dut.b_din.value = 0
    await RisingEdge(dut.clk)


async def write_port(dut, addr, data, port: str):
    """Write one word via port A or B (one clock cycle)."""

    if port.lower() == "a":
        dut.a_addr.value = addr
        dut.a_din.value = data
        dut.a_en.value = 1
        dut.a_wen.value = 1
        await RisingEdge(dut.clk)
        dut.a_en.value = 0
        dut.a_wen.value = 0

    if port.lower() == "b":
        dut.b_addr.value = addr
        dut.b_din.value = data
        dut.b_en.value = 1
        dut.b_wen.value = 1
        await RisingEdge(dut.clk)
        dut.b_en.value = 0
        dut.b_wen.value = 0


async def read_port(dut, addr, port: str):
    """Read one word from Port A or B and return the data (1-cycle latency)."""

    if port.lower() == "a":
        dut.a_addr.value = addr
        dut.a_en.value = 1
        dut.a_wen.value = 0
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        val = int(dut.a_dout.value)
        dut.a_en.value = 0

    if port.lower() == "b":
        dut.b_addr.value = addr
        dut.b_en.value = 1
        dut.b_wen.value = 0
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        val = int(dut.b_dout.value)
        dut.b_en.value = 0

    return val


@cocotb.test()
async def write_all_zeros(dut):
    await setup(dut)
    await write_port(dut, 1, 0x00000000, "A")
    val = await read_port(dut, 1, "A")
    assert val == 0x00000000, f"Expected 0, got 0x{val:08X}"

    await write_port(dut, 2, 0x00000000, "B")
    val = await read_port(dut, 2, "B")
    assert val == 0x00000000, f"Expected 0, got 0x{val:08X}"


@cocotb.test()
async def write_all_ones(dut):
    await setup(dut)
    await write_port(dut, 2, 0xFFFFFFFF, "A")
    val = await read_port(dut, 2, "A")
    assert val == 0xFFFFFFFF, f"Expected 0xFFFFFFFF, got 0x{val:08X}"

    await write_port(dut, 3, 0xFFFFFFFF, "B")
    val = await read_port(dut, 3, "B")
    assert val == 0xFFFFFFFF, f"Expected 0xFFFFFFFF, got 0x{val:08X}"


@cocotb.test()
async def write_read(dut):
    """Write via ports A and B, read back one cycle later."""
    await setup(dut)
    await write_port(dut, 5, 0xDEADBEEF, "A")
    val = await read_port(dut, 5, "A")
    assert val == 0xDEADBEEF, f"Expected 0xDEADBEEF, got 0x{val:08X}"

    await write_port(dut, 15, 0xFEEDFACE, "B")
    val = await read_port(dut, 15, "B")
    assert val == 0xFEEDFACE, f"Expected 0xFEEDFACE, got 0x{val:08X}"


@cocotb.test()
async def cross_write_read(dut):
    """Write different data on both ports to different addresses, verify cross-read."""
    await setup(dut)
    await write_port(dut, 20, 0x11111111, "A")
    await write_port(dut, 30, 0x22222222, "B")

    val_a = await read_port(dut, 20, "A")
    val_b = await read_port(dut, 30, "B")
    assert val_a == 0x11111111, f"Port A addr 20: got 0x{val_a:08X}"
    assert val_b == 0x22222222, f"Port B addr 30: got 0x{val_b:08X}"

    # Cross read: port B reads addr written by A, port A reads addr written by B
    val_cross_a = await read_port(dut, 30, "A")
    val_cross_b = await read_port(dut, 20, "B")
    assert val_cross_a == 0x22222222, f"Cross A->30: got 0x{val_cross_a:08X}"
    assert val_cross_b == 0x11111111, f"Cross B->20: got 0x{val_cross_b:08X}"


@cocotb.test()
async def concurrent_write_same_address(dut):
    """Both ports write to same address in same cycle; last write wins (B wins per simulation)."""
    await setup(dut)
    dut.a_addr.value = 50
    dut.a_din.value = 0xAAAAAAAA
    dut.a_en.value = 1
    dut.a_wen.value = 1

    dut.b_addr.value = 50
    dut.b_din.value = 0xBBBBBBBB
    dut.b_en.value = 1
    dut.b_wen.value = 1

    await RisingEdge(dut.clk)
    dut.a_en.value = 0
    dut.a_wen.value = 0
    dut.b_en.value = 0
    dut.b_wen.value = 0

    val = await read_port(dut, 50, "A")
    assert val == 0xBBBBBBBB, f"Expected 0xBBBBBBBB, got 0x{val:08X}"


@cocotb.test()
async def write_alternating_pattern(dut):
    """Write 0x55555555 and 0xAAAAAAAA, read back both."""
    await setup(dut)
    await write_port(dut, 3, 0x55555555, "A")
    await write_port(dut, 4, 0xAAAAAAAA, "A")
    v3 = await read_port(dut, 3, "A")
    v4 = await read_port(dut, 4, "A")
    assert v3 == 0x55555555, f"addr 3: got 0x{v3:08X}"
    assert v4 == 0xAAAAAAAA, f"addr 4: got 0x{v4:08X}"


@cocotb.test()
async def address_boundary_zero(dut):
    """Read and write at address 0."""
    await setup(dut)
    await write_port(dut, 0, 0x12345678, "A")
    val = await read_port(dut, 0, "A")
    assert val == 0x12345678, f"addr 0: got 0x{val:08X}"


@cocotb.test()
async def address_boundary_max(dut):
    """Read and write at address 511 (maximum for 512x32)."""
    await setup(dut)
    await write_port(dut, 511, 0xFEDCBA98, "A")
    val = await read_port(dut, 511, "A")
    assert val == 0xFEDCBA98, f"addr 511: got 0x{val:08X}"


@cocotb.test()
async def multiple_sequential_writes_then_reads(dut):
    """Write 8 locations sequentially, then read all back."""
    await setup(dut)
    test_data = {100 + i: 0xA0000000 + i for i in range(8)}
    for addr, val in test_data.items():
        await write_port(dut, addr, val, "A")
    for addr, expected in test_data.items():
        got = await read_port(dut, addr, "A")
        assert got == expected, (
            f"addr {addr}: expected 0x{expected:08X}, got 0x{got:08X}"
        )


@cocotb.test()
async def back_to_back_reads(dut):
    """Write two words, then read them back-to-back"""
    await setup(dut)
    await write_port(dut, 80, 0x0000AAAA, "A")
    await write_port(dut, 81, 0x0000BBBB, "A")
    dut.a_addr.value = 80
    dut.a_en.value = 1
    dut.a_wen.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    val80 = int(dut.a_dout.value)

    dut.a_addr.value = 81
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    val81 = int(dut.a_dout.value)
    dut.a_en.value = 0

    assert val80 == 0x0000AAAA, f"addr 80: got 0x{val80}"
    assert val81 == 0x0000BBBB, f"addr 81: got 0x{val81:08X}"
