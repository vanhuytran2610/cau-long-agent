# Badminton Admin Agent (FastAPI)

Agent quản lý ngày đánh cầu lông cho admin. FastAPI + LangGraph (Groq), gọi
ngược backend Express qua HTTP kèm JWT. FastAPI **không** đụng MongoDB của app
— mọi thao tác đi qua route Express có sẵn, nên logic tính tiền
(`calculateWithGroq`) vẫn nằm một chỗ.

```
React admin --(lệnh + JWT)--> FastAPI /agent --> LangGraph agent
                                                    |
                                       tools = httpx -> Express routes
                                                    |
                                          Express + MongoDB (giữ nguyên)
```

## Cấu trúc

```
app/
  main.py            FastAPI: /agent, /suggestions, /health; memory MongoDB
  agent.py           6 tool + system prompt + create_react_agent (Groq)
  express_client.py  httpx bọc các route Express, forward JWT
  suggestions.py     danh sách gợi ý (button) hiển thị cho admin
requirements.txt
.env.example
```

## Chạy local

```bash
pip install -r requirements.txt
cp .env.example .env      # điền GROQ_API_KEY, MONGODB_URI, EXPRESS_BASE_URL, CORS_ORIGINS
uvicorn app.main:app --reload --port 8000
```

MongoDB phải sẵn sàng lúc khởi động (dùng để lưu lịch sử hội thoại).

## Endpoints

| Method | Path           | Mô tả                                            |
|--------|----------------|--------------------------------------------------|
| GET    | `/health`      | Healthcheck                                      |
| GET    | `/suggestions` | Danh sách button gợi ý function                  |
| POST   | `/agent`       | Gửi lệnh tiếng Việt (cần header `Authorization: Bearer <jwt admin>`) |

`POST /agent` body: `{ "message": "tạo ngày 20/6", "thread_id": "optional" }`
→ `{ "reply": "...", "thread_id": "..." }`

`thread_id` mặc định suy từ JWT (mỗi admin một lịch sử). Truyền tay nếu muốn
nhiều cuộc chat song song.

## 4 việc agent làm (mỗi tool = 1 route Express)

| Việc          | Tool                | Route Express                       |
|---------------|---------------------|-------------------------------------|
| Tạo ngày      | `create_vote_date`  | POST /api/categories                |
| Tính tiền     | `calculate`         | POST /api/categories/:id/calculate  |
| Show kết quả  | `show_result`       | PUT  /api/categories/:id/export     |
| Sửa ngày      | `edit_date`         | PUT  /api/categories/:id            |
| Tra cứu       | `list_categories` / `list_participants` | GET ...          |

Hành động ghi (calculate / show / edit) sẽ được agent hỏi xác nhận trong chat
trước khi thực hiện (quy tắc trong system prompt).

## Tích hợp React (admin site)

```jsx
const AGENT_URL = "https://caulong-agent.vhuytran.dev";

// 1) Lấy button gợi ý khi mở chat
const { suggestions } = await (await fetch(`${AGENT_URL}/suggestions`)).json();

// 2) Gửi lệnh (gõ tay hoặc bấm button)
const res = await fetch(`${AGENT_URL}/agent`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${adminToken}`,   // token Express phát lúc login
  },
  body: JSON.stringify({ message: text }),
});
const { reply } = await res.json();
```

`CORS_ORIGINS` trong `.env` = domain của **trang admin**, không phải domain agent.

## Lưu ý

- Nếu format `sendResponse` của Express khác (không có field `data`), sửa
  `_unwrap` trong `express_client.py`.
- Dùng MongoDB Atlas thì whitelist IP server trong Atlas Network Access.
- `show_result` hiện nhận `qr_img_url`; route export cũng nhận `qr_img_id` nếu
  muốn chọn QR đã lưu sẵn.
