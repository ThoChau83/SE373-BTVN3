# -*- coding: utf-8 -*-
"""Harness: các lớp code kiểm soát agent.

BƯỚC 2 · Lớp 1: Ràng buộc là dữ liệu (slide S61–S63)
BƯỚC 3 · Lớp 3: Kiểm quyền (slide S41)
BƯỚC 4 · Lớp 2: Tiêu chí hoàn thành (slide S43–S44)
BƯỚC 5 · Lớp 4: Bàn giao (slide S48)
"""
from dataclasses import dataclass

from tools import BOOKINGS, find_flight


# frozen=True: tạo xong là KHÔNG ai sửa được (kể cả AI)
@dataclass(frozen=True)
class Constraints:
    origin: str          # điểm đi
    dest: str            # điểm đến
    date: str            # ngày bay
    depart_before: str   # phải bay trước giờ này
    max_price: int       # giá tối đa

    def violations(self, flight: dict) -> list[str]:
        """Chuyến này vi phạm những gì? Danh sách rỗng = hợp lệ."""
        problems = []
        if flight["depart"] >= self.depart_before:
            problems.append(f"bay lúc {flight['depart']}, không trước {self.depart_before}")
        if flight["price"] > self.max_price:
            problems.append(f"giá {flight['price']:,} vượt {self.max_price:,}")
        return problems


# Luật của công ty, cũng ghi thành dữ liệu
@dataclass(frozen=True)
class Policy:
    allowed_tools: tuple = ("search_flights", "check_seat", "book_seat", "pay", "get_booking")
    auto_pay_limit: int = 1_500_000      # vé đắt hơn mức này: phải hỏi sếp mới được pay


# ============================================== BƯỚC 3 · KIỂM QUYỀN
def check_permission(tool: str, args: dict, req: Constraints, policy: Policy) -> tuple[str, str]:
    """Người gác cổng. Chạy TRƯỚC khi bấm nút.

    Trả về (quyết định, lý do), quyết định là một trong:
        "ALLOW"      cho bấm
        "DENY"       cấm
        "ASK_HUMAN"  phải hỏi sếp
    """
    # 1. Chỉ được bấm các nút có trong danh sách
    if tool not in policy.allowed_tools:
        return "DENY", f"không được dùng tool '{tool}'"

    # 2. Giữ ghế: chuyến đó phải đúng yêu cầu của khách (dùng lớp 1 ở trên)
    if tool == "book_seat":
        flight = find_flight(args["flight_id"])
        if flight is None:
            return "DENY", "không có chuyến này"
        problems = req.violations(flight)
        if problems:
            return "DENY", "; ".join(problems)

    # 3. Trả tiền: vé đắt hoặc không hoàn tiền → phải hỏi sếp
    if tool == "pay":
        booking = BOOKINGS.get(args["booking_code"])
        if booking is None:
            return "DENY", "không có mã đặt chỗ này"
        if booking["price"] > policy.auto_pay_limit:
            return "ASK_HUMAN", f"giá {booking['price']:,} vượt hạn mức {policy.auto_pay_limit:,}"
        if not booking["refundable"]:
            return "ASK_HUMAN", "vé không hoàn tiền"

    return "ALLOW", ""


# ============================================== BƯỚC 4 · TIÊU CHÍ HOÀN THÀNH
def is_done(booking_code: str, req: Constraints) -> tuple[bool, dict]:
    """AI báo "xong" thì gọi hàm này. KHÔNG tin lời AI: tự mở vé ra kiểm.

    Trả về (đạt hay không, kết quả từng điều kiện).
    """
    b = BOOKINGS.get(booking_code)          # đọc thẳng từ hệ thống, không hỏi AI
    if b is None:
        return False, {"vé có tồn tại": False}
    checks = {
        "vé có tồn tại": True,
        "status == confirmed": b["status"] == "confirmed",
        "đã trả tiền": b["paid"],
        f"đúng ngày {req.date}": b["date"] == req.date,
        f"bay trước {req.depart_before}": b["depart"] < req.depart_before,
        f"giá <= {req.max_price:,}": b["price"] <= req.max_price,
    }
    return all(checks.values()), checks


# ============================================== BƯỚC 5 · BÀN GIAO
@dataclass
class Handoff:
    """Biên bản để lại khi agent phải dừng giữa chừng."""
    reason: str          # 1. vì sao dừng
    progress: str        # 2. đã làm tới đâu
    side_effects: list   #    việc đã làm thay đổi thế giới thật
    tried: list          # 3. đã thử những gì
    question: str        # 4. cần người trả lời câu gì

    def show(self) -> str:
        return "\n".join([
            f"⛔ DỪNG · {self.reason}",
            f"   Đã làm tới   : {self.progress}",
            f"   Tác dụng phụ : {'; '.join(self.side_effects) or 'không có'}",
            f"   Đã thử       : {' → '.join(self.tried)}",
            f"   Hỏi người    : {self.question}",
        ])


def current_side_effects() -> list[str]:
    """Đọc hệ thống xem đang có vé nào bị giữ / đã trừ tiền."""
    out = []
    for code, b in BOOKINGS.items():
        if b["paid"]:
            out.append(f"ĐÃ TRỪ TIỀN {b['price']:,}đ cho {code} ({b['flight_id']})")
        else:
            out.append(f"đang GIỮ GHẾ {code} ({b['flight_id']} ghế {b['seat']}), chưa trả tiền")
    return out


# --------------------------------------------- thử
def demo_step3():
    import tools
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)
    policy = Policy()

    def try_tool(name, args):
        """Hỏi người gác cổng trước. Chỉ bấm nút thật khi được ALLOW."""
        decision, reason = check_permission(name, args, req, policy)
        print(f"{name}({args})")
        print(f"   → {decision} {reason}")
        if decision == "ALLOW":
            result = getattr(tools, name)(**args)
            print(f"   → đã bấm, kết quả: {result}")
            return result

    try_tool("cancel_booking", {"booking_code": "BK-1001"})          # nút lạ
    try_tool("book_seat", {"flight_id": "QH118", "seat": "7D"})      # sai giờ
    try_tool("book_seat", {"flight_id": "VN122", "seat": "12A"})     # hợp lệ
    try_tool("pay", {"booking_code": "BK-1001"})                     # VN122 đắt → hỏi sếp
    try_tool("book_seat", {"flight_id": "VJ620", "seat": "3A"})      # hợp lệ
    try_tool("pay", {"booking_code": "BK-1002"})                     # VJ620 rẻ → cho trả


def demo_step4():
    import tools
    tools.BOOKINGS.clear()
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)

    # Tạo sẵn 3 vé (bấm thẳng tool, KHÔNG qua người gác, để giả lập AI làm ẩu)
    tools.book_seat("VJ620", "3A"); tools.pay("BK-1001")   # BK-1001: đúng hết
    tools.book_seat("VN122", "12A")                       # BK-1002: giữ ghế nhưng QUÊN trả tiền
    tools.book_seat("QH118", "7D"); tools.pay("BK-1003")  # BK-1003: chuyến 15:40, sai giờ

    # AI đều nói "xong rồi" cho cả 4 trường hợp dưới. Code kiểm lại:
    for code in ["BK-1001", "BK-1002", "BK-1003", "BK-9999"]:   # BK-9999: mã AI bịa ra
        ok, checks = is_done(code, req)
        print(f"AI nói: 'Đã đặt xong vé {code}'  →  code kiểm: {'ĐẠT ✓' if ok else 'KHÔNG ĐẠT ✗'}")
        for name, passed in checks.items():
            if not passed:
                print(f"      ✗ {name}")


def demo_step5():
    import tools
    tools.BOOKINGS.clear()
    req = Constraints("SGN", "DAD", "2026-10-07", depart_before="12:00", max_price=2_000_000)
    policy = Policy()
    tried = []                                   # ghi lại mọi nút đã bấm

    # Giả lập agent đi từng bước để đặt VN122
    steps = [("search_flights", {"origin": "SGN", "dest": "DAD", "date": "2026-10-07"}),
             ("check_seat", {"flight_id": "VN122"}),
             ("book_seat", {"flight_id": "VN122", "seat": "12A"}),
             ("pay", {"booking_code": "BK-1001"})]

    for name, args in steps:
        decision, reason = check_permission(name, args, req, policy)
        if decision == "ASK_HUMAN":              # không có sếp trực → phải dừng
            handoff = Handoff(
                reason=f"{name} cần sếp duyệt: {reason}",
                progress="đã giữ ghế, chưa trả tiền",
                side_effects=current_side_effects(),
                tried=tried,
                question=f"Có duyệt trả tiền vé {args['booking_code']} không? (có/không)",
            )
            print(handoff.show())
            return
        result = getattr(tools, name)(**args)
        tried.append(f"{name}={result['status']}")
        print(f"{name}  →  {result['status']}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("========== BƯỚC 3 · Kiểm quyền")
    demo_step3()
    print("\n========== BƯỚC 4 · Tiêu chí hoàn thành")
    demo_step4()
    print("\n========== BƯỚC 5 · Bàn giao")
    demo_step5()
