# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    # Set the clock period to 10 us (100 KHz)
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    
    # Nhả Reset để chip hoạt động
    dut.rst_n.value = 1

    dut._log.info("Test project behavior")

    # Test case 1: Đưa giá trị vào
    dut.ui_in.value = 20
    dut.uio_in.value = 30

    # BẮT BUỘC: Cho thời gian trôi đi (ví dụ 20 chu kỳ xung nhịp) để chip xử lý dữ liệu
    await ClockCycles(dut.clk, 20)

    # Test case 2: Đổi giá trị khác xem mạch phản ứng thế nào
    dut.ui_in.value = 55
    dut.uio_in.value = 10
    
    # Tiếp tục cho mạch chạy thêm 50 chu kỳ nữa
    await ClockCycles(dut.clk, 50)
