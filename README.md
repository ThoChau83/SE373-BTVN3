# SE373 · BTVN#3 · Agent đặt vé máy bay (LangChain + LangGraph + Gemini)

- 4 lớp harness: ràng buộc là dữ liệu, kiểm quyền, tiêu chí hoàn thành, bàn giao (`harness.py`)
- 3 mẫu agent: ReAct, Plan-then-Execute, Hybrid
- Đánh giá 3 mẫu trên 3 tình huống (`results.md`)

## Cài đặt

```bash
pip install -r requirements.txt
```

Copy `.env.example` thành `.env` rồi điền API key Gemini (lấy tại https://aistudio.google.com/apikey).

## Chạy

| Lệnh | Nội dung |
|---|---|
| `python tools.py` | 5 tool giả lập hệ thống bán vé |
| `python harness.py` | Thử các lớp harness (không cần API key) |
| `python agent_react.py 2` | Mẫu ReAct |
| `python agent_plan_execute.py 2` | Mẫu Plan-then-Execute |
| `python agent_hybrid.py 2` | Mẫu Hybrid |
| `python evaluate.py` | Đánh giá cả 3 mẫu → `results.md` |
