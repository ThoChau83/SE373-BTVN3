# -*- coding: utf-8 -*-
"""BƯỚC 8 · Agent Hybrid "ReAct + Plan" (slide S24).

Giống hệt Plan-then-Execute, chỉ khác 1 mũi tên: bước nào hỏng thì quay lại
cho AI lập kế hoạch MỚI (kèm thông tin lần trước hỏng ở đâu), thay vì dừng luôn.
Toàn bộ code nằm ở agent_plan_execute.py, chỉ bật công tắc replan=True.

    python agent_hybrid.py 1    yêu cầu đầy đủ
    python agent_hybrid.py 2    khách chỉ nói "rẻ nhất"
    python agent_hybrid.py 3    khách đòi chuyến VN122
"""
import sys

from agent_plan_execute import run
from harness import Constraints

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)
    case = sys.argv[1] if len(sys.argv) > 1 else "1"
    request_text = {
        "1": "Đặt 1 vé SGN đi DAD ngày 2026-10-07, bay trước 12:00, giá dưới 2 triệu.",
        "2": "Đặt vé rẻ nhất SGN đi DAD ngày 2026-10-07.",
        "3": "Đặt vé chuyến VN122 SGN đi DAD ngày 2026-10-07.",
    }[case]
    run(request_text, req, replan=True)       # ← khác Plan-then-Execute đúng chỗ này
