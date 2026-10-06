# -*- coding: utf-8 -*-
"""BƯỚC 1 · Tool giả lập: 5 "nút bấm" của hệ thống bán vé (slide S37)."""

# Dữ liệu chuyến bay gõ tay. Key = (điểm đi, điểm đến, ngày)
FLIGHTS = {
    ("SGN", "DAD", "2026-10-07"): [
        {"flight_id": "VJ620", "depart": "06:05", "price": 1_390_000, "refundable": True, "seats": ["3A", "3C"]},
        {"flight_id": "VN122", "depart": "08:10", "price": 1_850_000, "refundable": True, "seats": ["12A"]},
        {"flight_id": "QH118", "depart": "15:40", "price": 1_290_000, "refundable": True, "seats": ["7D"]},
    ],
    ("SGN", "HAN", "2026-10-08"): [
        {"flight_id": "VN210", "depart": "07:00", "price": 1_350_000, "refundable": True, "seats": ["20A"]},
        {"flight_id": "VJ130", "depart": "09:30", "price": 1_450_000, "refundable": True, "seats": ["5A"]},
    ],
}

# Chuyến "vừa có người mua mất ghế cuối": search vẫn thấy, nhưng check_seat báo hết
SOLD_OUT = {"VN210"}

BOOKINGS = {}  # các vé đã đặt: mã đặt chỗ -> thông tin vé


def find_flight(flight_id):
    for flights in FLIGHTS.values():
        for f in flights:
            if f["flight_id"] == flight_id:
                return f
    return None


def flight_date(flight_id):
    for (_, _, date), flights in FLIGHTS.items():
        if any(f["flight_id"] == flight_id for f in flights):
            return date
    return None


# ---------------------------------------------------------------- 5 tool
def search_flights(origin: str, dest: str, date: str) -> dict:
    """Tìm chuyến bay theo chặng và ngày (YYYY-MM-DD)."""
    flights = FLIGHTS.get((origin, dest, date), [])
    return {"status": "ok", "flights": flights}


def check_seat(flight_id: str) -> dict:
    """Xem chuyến còn ghế nào, giá bao nhiêu."""
    f = find_flight(flight_id)
    if f is None:
        return {"status": "not_found", "hint": "flight_id phải lấy từ search_flights"}
    if flight_id in SOLD_OUT:
        return {"status": "sold_out", "hint": "chuyến đã hết ghế, chọn chuyến khác"}
    return {"status": "ok", "flight_id": flight_id, "depart": f["depart"],
            "price": f["price"], "refundable": f["refundable"], "seats": f["seats"]}


def book_seat(flight_id: str, seat: str) -> dict:
    """Giữ 1 ghế. Chưa trả tiền (status = held)."""
    f = find_flight(flight_id)
    if f is None or flight_id in SOLD_OUT or seat not in f["seats"]:
        return {"status": "sold_out", "hint": "gọi check_seat để xem ghế còn trống"}
    code = f"BK-{1001 + len(BOOKINGS)}"
    BOOKINGS[code] = {"booking_code": code, "flight_id": flight_id, "seat": seat,
                      "date": flight_date(flight_id), "depart": f["depart"], "price": f["price"],
                      "refundable": f["refundable"], "paid": False, "status": "held"}
    return {"status": "held", "booking_code": code, "price": f["price"]}


def pay(booking_code: str) -> dict:
    """Trả tiền cho vé đang giữ. KHÔNG hoàn lại được."""
    b = BOOKINGS.get(booking_code)
    if b is None:
        return {"status": "not_found"}
    b["paid"], b["status"] = True, "confirmed"
    return {"status": "paid", "booking_code": booking_code}


def get_booking(booking_code: str) -> dict:
    """Đọc lại vé từ hệ thống để xác nhận."""
    return BOOKINGS.get(booking_code, {"status": "not_found"})


# --------------------------------------------- thử bấm tay từng nút
if __name__ == "__main__":
    print("1.", search_flights("SGN", "DAD", "2026-10-07"))
    print("2.", check_seat("VJ620"))
    r = book_seat("VJ620", "3A")
    print("3.", r)
    print("4.", pay(r["booking_code"]))
    print("5.", get_booking(r["booking_code"]))
