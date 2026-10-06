# -*- coding: utf-8 -*-
"""BƯỚC 9 · Đánh giá 3 mẫu agent trên cùng bộ tình huống.

    python evaluate.py

Chấm bằng CODE (không tin lời AI), đo 3 thứ cho mỗi lần chạy:
    kết quả      ĐẶT ĐƯỢC VÉ / CHỜ DUYỆT / DỪNG — có đúng với kỳ vọng không
    gọi AI       số lần gọi Gemini (= chi phí, độ chậm)
    bấm nút      số lần gọi tool
"""
import sys
import time

from langchain_core.callbacks import BaseCallbackHandler

import agent_plan_execute
import agent_react
import tools
from harness import Constraints, is_done

SCENARIOS = [
    ("S1", "Đặt 1 vé SGN đi DAD ngày 2026-10-07, bay trước 12:00, giá dưới 2 triệu.",
     Constraints("SGN", "DAD", "2026-10-07", "12:00", 2_000_000), "ĐẶT ĐƯỢC VÉ"),
    ("S2", "Đặt 1 vé SGN đi HAN ngày 2026-10-08, bay trước 12:00, giá dưới 2 triệu.",
     Constraints("SGN", "HAN", "2026-10-08", "12:00", 2_000_000), "ĐẶT ĐƯỢC VÉ"),
    ("S3", "Đặt vé chuyến VN122 SGN đi DAD ngày 2026-10-07.",
     Constraints("SGN", "DAD", "2026-10-07", "12:00", 2_000_000), "CHỜ DUYỆT"),
]

PATTERNS = {
    "ReAct": lambda text, req, cb: agent_react.run(text, req, callbacks=cb),
    "Plan-then-Execute": lambda text, req, cb: agent_plan_execute.run(text, req, replan=False, callbacks=cb),
    "Hybrid": lambda text, req, cb: agent_plan_execute.run(text, req, replan=True, callbacks=cb),
}


class CountAICalls(BaseCallbackHandler):
    """Đếm số lần gọi Gemini: LangChain tự gọi hàm này mỗi khi AI bắt đầu suy nghĩ."""
    def __init__(self):
        self.n = 0

    def on_chat_model_start(self, *args, **kwargs):
        self.n += 1


def grade(handoff, req) -> str:
    """Chấm kết quả bằng code."""
    code = list(tools.BOOKINGS)[-1] if tools.BOOKINGS else None
    if code and is_done(code, req)[0]:
        return "ĐẶT ĐƯỢC VÉ"
    if handoff and "duyệt" in handoff.reason:
        return "CHỜ DUYỆT"
    return "DỪNG"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = []
    for sid, text, req, expected in SCENARIOS:
        for name, run in PATTERNS.items():
            print(f"\n{'=' * 70}\n{sid} · {name}\n{'=' * 70}")
            tools.BOOKINGS.clear()                    # mỗi lần chạy bắt đầu sạch
            counter = CountAICalls()
            try:
                handoff, tried = run(text, req, [counter])
                result = grade(handoff, req)
            except Exception as e:                    # vd: hết lượt Gemini miễn phí
                print("LỖI:", str(e)[:200])
                result, tried = "LỖI", []
            rows.append((sid, name, expected, result, counter.n, len(tried)))
            time.sleep(2)                             # nghỉ chút cho đỡ bị giới hạn tốc độ

    # ----- bảng kết quả
    table = ["| Tình huống | Mẫu | Kỳ vọng | Kết quả | Đúng? | Gọi AI | Bấm nút |",
             "|---|---|---|---|:-:|--:|--:|"]
    for sid, name, expected, result, ai, nut in rows:
        table.append(f"| {sid} | {name} | {expected} | {result} | {'✓' if result == expected else '✗'} | {ai} | {nut} |")

    summary = ["| Mẫu | Đúng | Tổng gọi AI | Tổng bấm nút |", "|---|:-:|--:|--:|"]
    for name in PATTERNS:
        mine = [r for r in rows if r[1] == name]
        right = sum(r[2] == r[3] for r in mine)
        summary.append(f"| {name} | {right}/{len(mine)} | {sum(r[4] for r in mine)} | {sum(r[5] for r in mine)} |")

    md = "# Kết quả đánh giá\n\n## Chi tiết\n\n" + "\n".join(table) + \
         "\n\n## Tổng hợp\n\n" + "\n".join(summary) + "\n"
    print("\n\n" + md)
    with open("results.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("Đã lưu vào results.md")


if __name__ == "__main__":
    main()
