# Kết quả đánh giá

## Chi tiết

| Tình huống | Mẫu | Kỳ vọng | Kết quả | Đúng? | Gọi AI | Bấm nút |
|---|---|---|---|:-:|--:|--:|
| S1 | ReAct | ĐẶT ĐƯỢC VÉ | CHỜ DUYỆT | ✗ | 4 | 3 |
| S1 | Plan-then-Execute | ĐẶT ĐƯỢC VÉ | DỪNG | ✗ | 1 | 3 |
| S1 | Hybrid | ĐẶT ĐƯỢC VÉ | ĐẶT ĐƯỢC VÉ | ✓ | 2 | 7 |
| S2 | ReAct | ĐẶT ĐƯỢC VÉ | ĐẶT ĐƯỢC VÉ | ✓ | 7 | 6 |
| S2 | Plan-then-Execute | ĐẶT ĐƯỢC VÉ | DỪNG | ✗ | 1 | 2 |
| S2 | Hybrid | ĐẶT ĐƯỢC VÉ | ĐẶT ĐƯỢC VÉ | ✓ | 2 | 6 |
| S3 | ReAct | CHỜ DUYỆT | CHỜ DUYỆT | ✓ | 4 | 3 |
| S3 | Plan-then-Execute | CHỜ DUYỆT | CHỜ DUYỆT | ✓ | 1 | 3 |
| S3 | Hybrid | CHỜ DUYỆT | CHỜ DUYỆT | ✓ | 1 | 3 |

## Tổng hợp

| Mẫu | Đúng | Tổng gọi AI | Tổng bấm nút |
|---|:-:|--:|--:|
| ReAct | 2/3 | 15 | 12 |
| Plan-then-Execute | 1/3 | 3 | 8 |
| Hybrid | 3/3 | 5 | 16 |
