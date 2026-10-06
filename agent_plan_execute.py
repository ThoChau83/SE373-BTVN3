# -*- coding: utf-8 -*-
"""BƯỚC 7 · Agent Plan-then-Execute (slide S22–S23).

AI lập kế hoạch MỘT lần → code làm theo từng bước, không hỏi AI nữa.
Bước nào hỏng → dừng và bàn giao (kế hoạch cứng, không có đường lui).

Luồng chạy được vẽ bằng LangGraph:

    plan → execute → execute → ... → check_done → END
                 └── (bước hỏng) ──→ give_up → END

    python agent_plan_execute.py 1    yêu cầu đầy đủ
    python agent_plan_execute.py 2    khách chỉ nói "rẻ nhất"
    python agent_plan_execute.py 3    khách đòi chuyến VN122
"""
import logging
import os
import sys
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

import tools
from harness import Constraints, Handoff, Policy, check_permission, current_side_effects, is_done

logging.getLogger("google_genai").setLevel(logging.ERROR)   # tắt cảnh báo thừa của thư viện Google

# ---------------------------------------------- hình dạng của 1 kế hoạch
class Step(BaseModel):
    tool: Literal["search_flights", "check_seat", "book_seat", "pay", "get_booking"]
    origin: Optional[str] = None
    dest: Optional[str] = None
    date: Optional[str] = None
    flight_id: Optional[str] = None
    seat: Optional[str] = None
    booking_code: Optional[str] = None


class Plan(BaseModel):
    steps: list[Step]


PLANNER_PROMPT = """Bạn lập kế hoạch đặt vé máy bay. Yêu cầu của khách: {request}

Các tool, theo đúng thứ tự:
  search_flights(origin, dest, date) → check_seat(flight_id) → book_seat(flight_id, seat)
  → pay(booking_code) → get_booking(booking_code)

Bạn CHƯA biết có những chuyến nào, nên dùng chỗ trống để code điền sau:
  "$CHEAPEST" = chuyến rẻ nhất trong kết quả search_flights
  "$SEAT"     = ghế trống đầu tiên của chuyến đó
  "$BOOKING"  = mã đặt chỗ do book_seat trả về
Nếu khách chỉ định mã chuyến cụ thể thì ghi thẳng mã chuyến đó."""

# (Hybrid) Khi lập LẠI kế hoạch, cho AI biết lần trước hỏng ở đâu
REPLAN_PROMPT = """
KẾ HOẠCH LẦN TRƯỚC BỊ HỎNG: {reason}
Đã làm: {tried}
Các chuyến đã tìm được: {flights}
Chuyến đã bị loại, KHÔNG được chọn lại: {excluded}
Hãy lập kế hoạch MỚI. Bây giờ đã biết danh sách chuyến, có thể ghi thẳng mã chuyến."""

MAX_REPLANS = 2     # (Hybrid) lập lại tối đa 2 lần, tránh lặp mãi

ARGS_OF = {"search_flights": ["origin", "dest", "date"], "check_seat": ["flight_id"],
           "book_seat": ["flight_id", "seat"], "pay": ["booking_code"], "get_booking": ["booking_code"]}


# ---------------------------------------------- "bộ nhớ" của graph
class State(TypedDict):
    plan: list          # các bước AI đã lập
    i: int              # đang làm bước thứ mấy
    memory: dict        # giá trị thật để điền vào chỗ trống
    tried: list         # các nút đã bấm
    stop_reason: str    # khác rỗng = có bước hỏng
    excluded: list      # (Hybrid) các chuyến đã hỏng, không chọn lại
    can_retry: bool     # (Hybrid) False nếu hỏng vì cần sếp duyệt (lập lại cũng vô ích)
    replans: int        # (Hybrid) đã lập lại kế hoạch mấy lần
    handoff: object     # biên bản bàn giao (None nếu không phải dừng)


def fill_blanks(step: Step, memory: dict, excluded: list) -> dict:
    """Điền chỗ trống: "$CHEAPEST" → "QH118", ..."""
    args = {name: getattr(step, name) for name in ARGS_OF[step.tool]}
    flights = [f for f in memory.get("flights", []) if f["flight_id"] not in excluded]
    if flights:
        memory = {**memory, "$CHEAPEST": min(flights, key=lambda f: f["price"])["flight_id"]}
    return {k: memory.get(v, v) for k, v in args.items()}


def build_graph(planner, request_text: str, req: Constraints, policy: Policy, replan: bool):

    # Ô 1 · Lập kế hoạch (gọi AI)
    def plan(state: State):
        prompt = PLANNER_PROMPT.format(request=request_text)
        is_replan = bool(state["stop_reason"])
        if is_replan:                               # (Hybrid) lần lập lại: kể cho AI nghe chuyện cũ
            flights = [(f["flight_id"], f["depart"], f["price"]) for f in state["memory"].get("flights", [])]
            prompt += REPLAN_PROMPT.format(reason=state["stop_reason"], tried=state["tried"],
                                           flights=flights, excluded=state["excluded"])
        p = planner.invoke(prompt)
        print(f"{'LẬP LẠI KẾ HOẠCH' if is_replan else 'KẾ HOẠCH CỦA AI'}:")
        for n, s in enumerate(p.steps, 1):
            print(f"   {n}. {s.tool}({fill_blanks(s, {}, [])})")
        print()
        return {"plan": p.steps, "i": 0, "stop_reason": "", "replans": state["replans"] + is_replan}

    # Ô 2 · Làm 1 bước (code, không gọi AI)
    def execute(state: State):
        step = state["plan"][state["i"]]
        args = fill_blanks(step, state["memory"], state["excluded"])
        decision, reason = check_permission(step.tool, args, req, policy)   # Lớp 3
        print(f"   Bước {state['i'] + 1}: {step.tool}({args})  →  harness: {decision} {reason}")
        bad_flight = [args["flight_id"]] if "flight_id" in args else []

        if decision == "DENY":
            return {"stop_reason": f"{step.tool}({args}) bị cấm: {reason}",
                    "tried": state["tried"] + [f"{step.tool}=denied"],
                    "excluded": state["excluded"] + bad_flight}
        if decision == "ASK_HUMAN":
            return {"stop_reason": f"{step.tool} cần sếp duyệt: {reason}", "can_retry": False}

        result = getattr(tools, step.tool)(**args)                           # bấm nút thật
        memory = dict(state["memory"])
        if step.tool == "search_flights":
            memory["flights"] = result["flights"]
        if step.tool == "check_seat" and result["status"] == "ok":
            memory["$SEAT"] = result["seats"][0]
        if step.tool == "book_seat" and result["status"] == "held":
            memory["$BOOKING"] = result["booking_code"]

        tried = state["tried"] + [f"{step.tool}={result['status']}"]
        if result["status"] not in ("ok", "held", "paid", "confirmed"):
            return {"stop_reason": f"{step.tool}({args}) trả về {result['status']}", "tried": tried,
                    "memory": memory, "excluded": state["excluded"] + bad_flight}
        return {"i": state["i"] + 1, "memory": memory, "tried": tried}

    # Ô 3 · Có bước hỏng → kế hoạch cứng không có đường lui → bàn giao     (Lớp 4)
    def give_up(state: State):
        handoff = Handoff(reason=state["stop_reason"],
                          progress=f"làm được {state['i']}/{len(state['plan'])} bước của kế hoạch",
                          side_effects=current_side_effects(),
                          tried=state["tried"],
                          question="Kế hoạch bị hỏng. Duyệt / lập kế hoạch mới / huỷ?")
        print("\nKẾT QUẢ:", handoff.show())
        return {"handoff": handoff}

    # Ô 4 · Làm hết kế hoạch → kiểm vé bằng code                          (Lớp 2)
    def check_done(state: State):
        code = state["memory"].get("$BOOKING")
        ok, _ = is_done(code, req)
        print(f"\nKẾT QUẢ: harness kiểm vé {code}: {'ĐẠT ✓' if ok else 'KHÔNG ĐẠT ✗'}")
        return {}

    # Mũi tên sau ô execute: đi tiếp, dừng, hay kiểm vé?
    def next_box(state: State):
        if state["stop_reason"]:
            if replan and state["can_retry"] and state["replans"] < MAX_REPLANS:
                return "plan"          # ← (Hybrid) MŨI TÊN DUY NHẤT KHÁC BIỆT: quay lại lập kế hoạch
            return "give_up"           # ← Plan-then-Execute: dừng, bàn giao
        if state["i"] >= len(state["plan"]):
            return "check_done"
        return "execute"

    g = StateGraph(State)
    g.add_node("plan", plan)
    g.add_node("execute", execute)
    g.add_node("give_up", give_up)
    g.add_node("check_done", check_done)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_conditional_edges("execute", next_box, ["execute", "plan", "give_up", "check_done"])
    g.add_edge("give_up", END)
    g.add_edge("check_done", END)
    return g.compile()


def run(request_text: str, req: Constraints, replan: bool = False, callbacks=None):
    """Chạy agent. Trả về (biên bản bàn giao hoặc None, danh sách nút đã bấm)."""
    load_dotenv()
    planner = ChatGoogleGenerativeAI(model=os.environ["GEMINI_MODEL"]).with_structured_output(Plan)
    graph = build_graph(planner, request_text, req, Policy(), replan)
    print(f"Khách: {request_text}\n")
    final = graph.invoke({"plan": [], "i": 0, "memory": {}, "tried": [], "stop_reason": "",
                          "excluded": [], "can_retry": True, "replans": 0, "handoff": None},
                         {"callbacks": callbacks or []})
    return final["handoff"], final["tried"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)
    case = sys.argv[1] if len(sys.argv) > 1 else "1"
    request_text = {
        "1": "Đặt 1 vé SGN đi DAD ngày 2026-10-07, bay trước 12:00, giá dưới 2 triệu.",
        "2": "Đặt vé rẻ nhất SGN đi DAD ngày 2026-10-07.",
        "3": "Đặt vé chuyến VN122 SGN đi DAD ngày 2026-10-07.",
    }[case]
    run(request_text, req)
