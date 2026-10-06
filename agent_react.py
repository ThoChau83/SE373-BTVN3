# -*- coding: utf-8 -*-
"""BƯỚC 6 · Agent ReAct (slide S18–S21): Gemini tự bấm nút, harness đứng canh.

ReAct = lặp lại: AI suy nghĩ → bấm 1 nút → xem kết quả → suy nghĩ tiếp ...

    python agent_react.py 1    yêu cầu đầy đủ
    python agent_react.py 2    khách chỉ nói "rẻ nhất", quên dặn giờ bay
    python agent_react.py 3    khách đòi chuyến VN122 (đắt → cần sếp duyệt)
"""
import json
import os
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware, hook_config
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

import tools
from harness import Constraints, Handoff, Policy, check_permission, current_side_effects, is_done

SYSTEM_PROMPT = """Bạn là nhân viên đặt vé máy bay. Chỉ dùng tool, không tự bịa thông tin.
Thứ tự: search_flights → check_seat → book_seat → pay → get_booking.
Nếu tool trả status "denied" hoặc "sold_out", đọc lý do rồi chọn chuyến khác.
Khi xong, trả lời ngắn: mã chuyến, giờ bay, giá, mã đặt chỗ."""


class HarnessMiddleware(AgentMiddleware):
    """Cắm harness (bước 2–5) vào vòng lặp của agent."""

    def __init__(self, req: Constraints, policy: Policy):
        super().__init__()
        self.req, self.policy = req, policy
        self.tried = []          # các nút đã bấm (cho biên bản bàn giao)
        self.handoff = None      # có biên bản = phải dừng

    def stop_with_handoff(self):
        return {"jump_to": "end", "messages": [AIMessage(content=self.handoff.show())]}

    # (1) Mỗi lần AI muốn bấm nút → hỏi người gác cổng trước   [Lớp 3 · Kiểm quyền]
    def wrap_tool_call(self, request, handler):
        name, args = request.tool_call["name"], request.tool_call["args"]
        call_id = request.tool_call["id"]
        decision, reason = check_permission(name, args, self.req, self.policy)
        print(f"   AI bấm: {name}({args})  →  harness: {decision} {reason}")

        if decision == "DENY":                      # cấm: báo lại cho AI để nó đổi hướng
            self.tried.append(f"{name}=denied")
            return ToolMessage(json.dumps({"status": "denied", "reason": reason}, ensure_ascii=False),
                               tool_call_id=call_id)

        if decision == "ASK_HUMAN":                 # không có sếp trực → lập biên bản  [Lớp 4]
            self.handoff = Handoff(
                reason=f"{name} cần sếp duyệt: {reason}",
                progress="đã giữ ghế, chưa trả tiền",
                side_effects=current_side_effects(),
                tried=self.tried,
                question=f"Có duyệt {name}({args}) không? (có/không)")
            return ToolMessage('{"status": "waiting_for_approval"}', tool_call_id=call_id)

        result = handler(request)                   # ALLOW: bấm nút thật
        self.tried.append(f"{name}={json.loads(result.content).get('status')}")
        return result

    # (2) Trước mỗi lần AI suy nghĩ: nếu đã có biên bản thì dừng luôn
    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        if self.handoff:
            return self.stop_with_handoff()
        return None

    # (3) Sau mỗi lần AI suy nghĩ
    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        last = state["messages"][-1]
        if last.tool_calls:
            return None                              # AI còn muốn bấm nút → cứ tiếp tục

        # AI nói "xong rồi" → KHÔNG tin, kiểm bằng code   [Lớp 2 · Tiêu chí hoàn thành]
        code = list(tools.BOOKINGS)[-1] if tools.BOOKINGS else None
        ok, checks = is_done(code, self.req)
        print(f"   AI nói xong. Harness kiểm vé {code}: {'ĐẠT ✓' if ok else 'KHÔNG ĐẠT ✗'}")
        if ok:
            return None
        self.handoff = Handoff(
            reason="AI báo xong nhưng vé không đạt: " + ", ".join(k for k, v in checks.items() if not v),
            progress="chưa đặt được vé hợp lệ",
            side_effects=current_side_effects(),
            tried=self.tried,
            question="Nới yêu cầu (giờ bay, giá) hay huỷ?")
        return self.stop_with_handoff()


def run(request_text: str, req: Constraints, callbacks=None):
    """Chạy agent. Trả về (biên bản bàn giao hoặc None, danh sách nút đã bấm)."""
    load_dotenv()
    model = ChatGoogleGenerativeAI(model=os.environ["GEMINI_MODEL"])
    harness = HarnessMiddleware(req, Policy())
    agent = create_agent(
        model=model,
        tools=[tool(f) for f in (tools.search_flights, tools.check_seat, tools.book_seat,
                                 tools.pay, tools.get_booking)],
        system_prompt=SYSTEM_PROMPT,
        middleware=[ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),   # ngân sách
                    harness],
    )
    print(f"Khách: {request_text}\n")
    result = agent.invoke({"messages": [{"role": "user", "content": request_text}]},
                          {"callbacks": callbacks or []})
    print("\nKẾT QUẢ:", result["messages"][-1].text)
    return harness.handoff, harness.tried


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    # Ràng buộc THẬT của khách (dữ liệu) — giống nhau ở cả 3 trường hợp
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)

    case = sys.argv[1] if len(sys.argv) > 1 else "1"
    request_text = {
        "1": "Đặt 1 vé SGN đi DAD ngày 2026-10-07, bay trước 12:00, giá dưới 2 triệu.",
        "2": "Đặt vé rẻ nhất SGN đi DAD ngày 2026-10-07.",
        "3": "Đặt vé chuyến VN122 SGN đi DAD ngày 2026-10-07.",
    }[case]
    run(request_text, req)
