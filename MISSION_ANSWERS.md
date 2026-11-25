# Day 14 Lab — Mission Answers

> **Học viên:** Bùi Lê Công Tuấn (`2A202603610`)  
> **Lớp:** K5-L3A

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secret trong mã nguồn (dòng 17–18):**
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - Rủi ro: Khi push lên Git, mọi secret bị lộ công khai trong lịch sử commit và khó thay đổi theo từng môi trường.
   - Đã sửa trong `production/config.py` (dòng 27, 32): đọc qua `os.getenv("OPENAI_API_KEY", "")` và `os.getenv("AGENT_API_KEY", "")`.
2. **Không có cấu hình tách biệt theo môi trường (dòng 21–22):**
   - `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng. Không thể chuyển giữa dev/staging/production mà không sửa code.
   - Đã sửa trong `production/config.py` (dòng 15–35): quản lý tập trung bằng dataclass `Settings` đọc từ biến môi trường và có hàm `validate()` fail-fast.
3. **Dùng `print()` và làm rò rỉ secret ra log (dòng 33–38):**
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` in thẳng API key ra stdout và không có format cấu trúc để các hệ thống thu thập log phân tích.
   - Đã sửa trong `production/app.py` (dòng 28–32, 111–122): dùng `logging` định dạng JSON có cấu trúc và tuyệt đối không log secret.
4. **Thiếu Health Check & Readiness Check (dòng 42–43):**
   - Không có `/health` và `/ready`, nên cloud platform / load balancer không biết container còn sống hay sẵn sàng nhận traffic để tự restart hoặc định tuyến.
   - Đã sửa trong `production/app.py` (dòng 135–161): bổ sung `GET /health` và `GET /ready`.
5. **Hardcode host `localhost`, port `8000` và bật `reload=True` (dòng 49–53):**
   - `host="localhost"` khiến app không nhận được kết nối từ bên ngoài container; `port=8000` không dùng biến `PORT` do cloud platform cấp; `reload=True` gây tốn tài nguyên và không ổn định trên production.
   - Đã sửa trong `production/app.py` (dòng 194–199): bind `0.0.0.0`, đọc `PORT`, tắt `reload` khi `DEBUG=false`.
6. **Không xử lý Graceful Shutdown:**
   - Khi nhận `SIGTERM` từ container orchestrator, tiến trình bị tắt đột ngột, dễ cắt ngang request đang xử lý.
   - Đã sửa trong `production/app.py` (dòng 40–68, 180–189): dùng `lifespan` của FastAPI và đăng ký xử lý `SIGTERM`.

---

### Exercise 1.2: Kết quả chạy thử bản `develop`

```text
$ curl.exe -sS -i -X POST "http://127.0.0.1:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 07:44:38 GMT
server: uvicorn
content-length: 126
content-type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Kết quả test bản `production`:
```text
$ curl.exe -sS -i "http://127.0.0.1:8000/health"
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":1.6,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T07:44:41.537233+00:00"}

$ curl.exe -sS -i -X POST "http://127.0.0.1:8000/ask" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

---

### Exercise 1.3: Bảng so sánh `develop` vs `production`

| Feature | Develop (`develop/app.py`) | Production (`production/app.py` + `config.py`) | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `MAX_TOKENS` trong code | Đọc toàn bộ từ env vars (`os.getenv`), kiểm tra hợp lệ qua `Settings.validate()` | Tránh lộ secret trên Git; triển khai cùng một artifact lên dev/staging/prod chỉ bằng cách đổi biến môi trường (12-Factor III). |
| **Logging** | Dùng `print()` tự do, in cả `OPENAI_API_KEY` | Dùng `logging` với format JSON (`{"time":..., "level":..., "msg":...}`), không log secret | Log aggregator (Loki, Datadog, Cloud Logging) parse và truy vấn được theo trường; bảo mật thông tin nhạy cảm. |
| **Health Check** | Không có `/health` hay `/ready` | Có `GET /health` (liveness) và `GET /ready` (readiness) | Platform/load balancer tự động kiểm tra sức khỏe container, chỉ route traffic khi sẵn sàng và tự restart khi app treo. |
| **Shutdown** | Tắt đột ngột khi process dừng | Dùng `lifespan` + handler `SIGTERM` để hoàn thành request đang chạy trước khi tắt | Tránh lỗi 502/connection reset cho người dùng khi deploy phiên bản mới hoặc scale down (zero-downtime deploy). |
| **Network Binding & Port** | `host="localhost"`, `port=8000`, `reload=True` | `host="0.0.0.0"`, `port=PORT` từ env, `reload=settings.debug` | Container cần bind `0.0.0.0` để nhận traffic từ bên ngoài; cloud platform cấp `PORT` động qua biến môi trường. |
| **CORS & Input** | Không cấu hình CORS, `question` qua query param | `CORSMiddleware` giới hạn origins/methods, nhận JSON body và validate rỗng (422) | Kiểm soát nguồn gọi hợp lệ từ trình duyệt và chuẩn hóa contract API. |

---

## Part 2: Docker

### Exercise 2.1: Trả lời câu hỏi về `02-docker/develop/Dockerfile`

1. **Base image là gì?**
   - `python:3.11` (bản đầy đủ của Debian + Python 3.11 + compiler/tools, dung lượng lớn ~1 GB).
2. **Working directory là gì?**
   - `/app` (`WORKDIR /app`). Mọi lệnh `COPY`, `RUN`, `CMD` sau đó thực thi tương đối trong `/app`.
3. **Tại sao `COPY requirements.txt` đứng trước `COPY . .`?**
   - Để tận dụng **Docker layer cache**. `requirements.txt` ít thay đổi hơn mã nguồn; khi chỉ sửa code (`app.py`), Docker dùng lại layer đã `pip install` từ cache mà không phải tải và cài lại toàn bộ thư viện.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   - `ENTRYPOINT` định nghĩa lệnh thực thi cố định của container (khó ghi đè, các tham số truyền vào `docker run` sẽ nối thêm làm argument).
   - `CMD` cung cấp lệnh hoặc tham số mặc định có thể bị ghi đè dễ dàng khi truyền lệnh mới ở cuối `docker run <image> <command>`.

---

### Exercise 2.2: Build và chạy container `my-agent:develop`

Lệnh build từ gốc repo:
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name cp2-dev-test -p 8000:8000 my-agent:develop
```

Kết quả gọi thử container:
```text
$ curl.exe -sS -i -X POST "http://127.0.0.1:8000/ask?question=What+is+Docker"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 07:48:37 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

---

### Exercise 2.3: Multi-stage build & So sánh kích thước image

- **Stage 1 (`builder`):** Dùng `python:3.11-slim`, cài `gcc`, `libpq-dev` và chạy `pip install --no-cache-dir --user -r requirements.txt` vào `/root/.local`.
- **Stage 2 (`runtime`):** Dùng `python:3.11-slim` sạch, chỉ copy thư mục `/root/.local` đã cài sẵn từ `builder` sang `/home/appuser/.local`, tạo user non-root `appuser`, copy source code + `utils/mock_llm.py`, thiết lập `HEALTHCHECK` và chạy `uvicorn`.
- **Tại sao image nhỏ hơn?** Không mang theo `gcc`, `libpq-dev`, apt cache hay các build artifact trung gian vào image cuối cùng, lại dùng base `python:3.11-slim` thay vì `python:3.11` đầy đủ.

Số liệu đo thực tế bằng `docker images my-agent`:
- **Develop (`my-agent:develop`):** `1.67 GB` (~1710 MB / `1.67GB` theo `docker images`)
- **Production (`my-agent:advanced`):** `240 MB`
- **Chênh lệch:** giảm **`1.43 GB` (~`85.6%`)** so với bản `develop`.

---

### Exercise 2.4: Docker Compose stack

Sơ đồ kiến trúc các service trong `02-docker/production/docker-compose.yml`:

```text
Client (:80 / :443)
   │
   ▼
[ nginx ] (nginx:alpine, reverse proxy)
   │  (network: internal)
   ▼
[ agent ] (FastAPI :8000, depends_on redis & qdrant healthy)
   ├──▶ [ redis ]  (redis:7-alpine :6379 — session cache & rate limiting)
   └──▶ [ qdrant ] (qdrant/qdrant:v1.9.0 :6333 — vector DB cho RAG)
```

Các service giao tiếp với nhau qua mạng bridge `internal` bằng tên service (`redis:6379`, `http://qdrant:6333`, `agent:8000`). Chỉ `nginx` mở cổng `80`/`443` ra ngoài host.

Kết quả test qua Nginx (`docker compose -p k5-day14-docker up -d --build`):
```text
$ curl.exe -sS -i "http://127.0.0.1/health"
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"status":"ok","uptime_seconds":7.0,"version":"2.0.0","timestamp":"2026-11-25T07:49:11.962197"}

$ curl.exe -sS -i -X POST "http://127.0.0.1/ask" -H "Content-Type: application/json" -d '{"question":"Explain_microservices"}'
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)
- **Kiểm tra ở đâu:** Trong dependency `verify_api_key` dùng `APIKeyHeader(name="X-API-Key", auto_error=False)` và tiêm vào `/ask` qua `Depends(verify_api_key)`.
- **Sai/thiếu key:** Thiếu header → trả `401 Unauthorized`; sai key → trong mẫu `develop` trả `403 Forbidden` (ở Part 6 chuẩn hóa đều trả `401`).
- **Rotate key:** Đổi giá trị biến môi trường `AGENT_API_KEY` rồi restart/redeploy (hoặc hỗ trợ danh sách key cũ + mới trong giai đoạn chuyển tiếp để zero-downtime rotation).

Kết quả test bản `develop`:
```text
# Không có key → 401
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Có key (X-API-Key: secret-key-123) → 200
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)
- **Thuật toán Rate Limiting (`rate_limiter.py`):** **Sliding Window Counter** lưu bằng `deque` timestamps cho từng `user_id`. Mỗi request sẽ xóa các timestamp cũ hơn `now - 60s`, nếu `len(window) >= max_requests` thì trả `429 Too Many Requests` kèm `Retry-After`.
- **Giới hạn theo role:** Tài khoản thường (`student`, role `user`) giới hạn **10 requests/phút** (`rate_limiter_user`); tài khoản admin (`teacher`, role `admin`) dùng `rate_limiter_admin` giới hạn **100 requests/phút** (hoặc có thể bypass limit cho role `admin`).

Kết quả test thực tế với tài khoản `student` / `demo123` (lấy JWT từ `POST /auth/token`, token đã che):

1. **Không có token → `401`:**
```text
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

2. **Có JWT hợp lệ (`Authorization: Bearer <REDACTED_TOKEN>`) → `200`:**
```text
HTTP/1.1 200 OK
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY

{"question":"Explain_JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.8e-05}}
```

3. **Vòng lặp gọi liên tiếp vượt 10 req/phút → `429` ở request thứ 10 trong vòng lặp (request thứ 11 tổng cộng):**
```text
Req 1..9: HTTP/1.1 200 OK
Req 10:   HTTP/1.1 429 Too Many Requests
retry-after: 59
x-ratelimit-limit: 10
x-ratelimit-remaining: 0

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost Guard & Vì sao cần cả Rate Limit lẫn Cost Guard
- **Cách triển khai Cost Guard với Redis:** Trước khi gọi LLM (`check_budget`), đọc tổng chi phí hiện tại trong Redis theo key ngày/tháng (vd `cost:daily:YYYY-MM-DD` hoặc `budget:{user_id}:{YYYY-MM}`); nếu đã vượt ngưỡng (`DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`), chặn ngay bằng `HTTP 402 Payment Required`. Sau khi LLM trả về (`record_cost`), tính chi phí theo `input_tokens` và `output_tokens` rồi cộng nguyên tử vào Redis bằng `INCRBYFLOAT` kèm `EXPIRE` tương ứng.
- **Vì sao cần cả hai:** **Rate Limit** bảo vệ *tốc độ / lưu lượng* (chống spam, DDoS, cạn CPU/worker trong ngắn hạn), còn **Cost Guard** bảo vệ *tiền / ngân sách* (ngay cả khi attacker gửi đúng tốc độ cho phép 10 req/phút nhưng mỗi prompt dài tối đa token hoặc dùng model đắt tiền trong nhiều giờ, chi phí vẫn tăng vọt nếu không có trần ngân sách).

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Check (`/health`) vs Readiness Check (`/ready`)

- **`GET /health` (Liveness probe):** Kiểm tra *tiến trình có còn sống không*. Nếu fail hoặc timeout, platform (Railway, Render, Kubernetes) sẽ **restart container**. Endpoint này phải độc lập với Redis/DB để tránh restart vòng lặp (crash loop) khi dependency bên ngoài chỉ tạm gián đoạn.
- **`GET /ready` (Readiness probe):** Kiểm tra *instance đã sẵn sàng nhận traffic chưa* (đã load xong model, kết nối được Redis/DB, chưa ở trạng thái shutdown). Nếu trả `503 Service Unavailable`, Load Balancer sẽ tạm **ngừng gửi request** vào instance đó (nhưng không kill container) cho đến khi sẵn sàng trở lại.

### Exercise 5.2: Graceful Shutdown (`SIGTERM`)
- Khi container orchestrator muốn dừng hoặc thay thế instance (rolling deploy, scale down), nó gửi tín hiệu `SIGTERM` (cho phép ứng dụng bắt và xử lý, khác với `SIGKILL` giết tiến trình ngay lập tức).
- Ứng dụng thực hiện:
  1. Đánh dấu trạng thái không còn ready (`/ready` trả 503) để ngừng nhận request mới.
  2. Chờ các request đang xử lý (in-flight requests) hoàn thành (thông qua `uvicorn` + `lifespan` shutdown, `timeout_graceful_shutdown`).
  3. Đóng kết nối Redis/DB sạch sẽ và thoát với exit code `0`.

### Exercise 5.3–5.5: Stateless Design & Load Balancing (3 instances + Redis + Nginx)
- **Tại sao state trong RAM bị hỏng khi scale nhiều instance?** Mỗi container/worker có vùng nhớ riêng (`conversation_history = {}`). Khi Nginx cân bằng tải theo round-robin, request 1 có thể vào `agent-1`, request 2 vào `agent-2` (không có dữ liệu của request 1) làm mất ngữ cảnh hội thoại.
- **Giải pháp Stateless:** Đẩy toàn bộ session/history và rate limit sang **Redis** dùng chung (`session:{session_id}`). Mọi instance đều đọc/ghi cùng một nguồn dữ liệu, có thể scale ngang hoặc restart từng instance mà không mất phiên làm việc.

Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python test_stateless.py`:

```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 79b9bf9b-f900-4441-ac40-94159da6468f

Request 1: [instance-47fe56]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-54018a]
  Q: Why do we need containers?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

Request 3: [instance-0373ed]
  Q: What is Kubernetes?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 4: [instance-47fe56]
  Q: How does load balancing work?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 5: [instance-54018a]
  Q: What is Redis used for?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-0373ed', 'instance-47fe56', 'instance-54018a'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  ...
✅ Session history preserved across all instances via Redis!
```

**Giải thích:** 5 requests liên tiếp thuộc cùng 1 `session_id` được Nginx phân phối qua cả **3 container khác nhau** (`instance-47fe56`, `instance-54018a`, `instance-0373ed`), nhưng tổng hợp lịch sử cuối cùng vẫn đủ **10 messages (5 turns)** nhờ toàn bộ session state được lưu tập trung trong Redis.

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Triển khai lên Cloud & So sánh `railway.toml` vs `render.yaml`

- **URL public & hướng dẫn kiểm tra:** xem [DEPLOYMENT.md](DEPLOYMENT.md) *(cần đăng nhập tài khoản Railway/Render cá nhân trên máy để lấy domain public và chụp 3 ảnh `dashboard.png`, `running.png`, `test.png`)*.
- **So sánh `railway.toml` với `render.yaml`:**
  - **Định dạng & phạm vi:** `railway.toml` dùng định dạng **TOML** cấu hình cho một service đơn lẻ (cách build, healthcheck, restart policy), còn biến môi trường và Redis add-on thường được cấu hình trên Dashboard/CLI. `render.yaml` là **Blueprint (YAML)** theo hướng Infrastructure-as-Code khai báo toàn bộ kiến trúc đa service (web service, Redis, envVars) trong một file.
  - **Cấu hình build & deploy:** `railway.toml` khai báo `[build] builder = "DOCKERFILE"` và `[deploy] healthcheckPath = "/health"`, `restartPolicyType`. `render.yaml` khai báo `type: web`, `runtime: docker`, `dockerfilePath`, `healthCheckPath: /health`.
  - **Quản lý biến môi trường & secret:** `render.yaml` hỗ trợ khai báo trực tiếp `envVars` với `generateValue: true` (tự sinh random secret như `AGENT_API_KEY`) hoặc `sync: false` (nhắc người dùng nhập secret như `REDIS_URL` trên dashboard mà không lưu vào Git).

### Exercise 3.3: Pipeline CI/CD Google Cloud Run (`03-cloud-deployment/production-cloud-run/`)

Đọc từ `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD trên GCP đi qua 4 bước tuần tự khi push lên nhánh `main`:
1. **Test (`test`):** Dùng `python:3.11-slim` cài `requirements.txt` + `pytest` và chạy `pytest tests/ -v` để kiểm thử tự động trước khi đóng gói.
2. **Build (`build`):** Dùng `gcr.io/cloud-builders/docker` build Docker image gắn 2 tag (`$COMMIT_SHA` và `latest`), tận dụng `--cache-from` để tăng tốc.
3. **Push (`push`):** Đẩy toàn bộ tag của image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`deploy`):** Gọi `gcloud run deploy` triển khai lên Cloud Run (`asia-southeast1`), cấu hình public access, autoscaling (`min-instances=1` tránh cold start, `max-instances=10`, concurrency `80`), tài nguyên (`512Mi`/`1 CPU`), liveness/startup probes (`/health`, `/ready`) và inject secret (`OPENAI_API_KEY`, `AGENT_API_KEY`) an toàn từ **Secret Manager** (không hardcode).

---

## Part 6: Final Project (`06-lab-complete/`)

Kết quả chạy `python check_production_ready.py` (chế độ đầy đủ có Docker và POSIX SIGTERM):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

- Kích thước image đo thực tế: **238 MB** (< 500 MB).
- `docker stop` tắt container với exit code **0** trong **0.7s** (< 10s).

---

## AI Log (theo `RULES.md`)

1. **Part 1–5 (Giải thích khái niệm & đối chiếu anti-pattern):**
   - *Hỏi gì:* Đối chiếu nhanh các anti-pattern giữa `develop/` và `production/` ở Part 1, 2, 4, 5 và tổng hợp lệnh test khớp với lưu ý lớp K5.
   - *Nhận gì:* Danh sách ánh xạ theo dòng code thực tế và kịch bản chạy `docker compose` tách `-p` tránh trùng tên project.
   - *Tự kiểm tra:* Tự chạy toàn bộ server/container trên máy (`curl -i`, `docker images`, `test_stateless.py`), lấy trực tiếp output HTTP, kích thước MB và kết quả Redis/Nginx để điền vào báo cáo.
2. **Part 6 (`06-lab-complete/`):**
   - *Hỏi gì:* Thiết kế cấu trúc các module `config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile` multi-stage và `docker-compose.yml` đáp ứng đủ 12 tiêu chí.
   - *Nhận gì:* Code sliding-window rate limit trên Redis sorted set, cost guard dùng `INCRBYFLOAT`, JSON formatter, giữ lại SIGTERM handler của `uvicorn`, và `CMD` lắng nghe `$PORT` làm PID 1.
   - *Tự sửa & tự kiểm tra:* Chạy `python check_production_ready.py --static-only` và chạy bản đầy đủ trong Linux container có Docker socket + `--network host` để xác nhận **PASS 12/12 (43/43 checks)** (bao gồm POSIX SIGTERM, image 238 MB < 500 MB, `docker stop` 0.7s).
3. **Part 7 (`benchmark-observability/`):**
   - *Hỏi gì:* Cách thêm Histogram `agent_question_length_chars` tránh cardinality cao, bổ sung `KNOWLEDGE_BASE` cho 2 câu sai (`security-02`, `scaling-03`), và sửa lỗi thiếu `PYTHONUSERBASE` trong `production/Dockerfile` khi chạy Docker stack.
   - *Nhận gì:* Snippet metric Histogram, 2 entry KB mới, file `.github/workflows/eval.yml`, và dòng `ENV PYTHONUSERBASE=/home/agent/.local` giúp container agent khởi động bình thường.
   - *Tự sửa & tự kiểm tra:* Tự chạy toàn bộ `load_test.py`, `run_eval.py` (`100% 23/23`, 0 regression), `promtool test rules`, Locust headless (`--no-deps` giữ đủ 3 instance khi `scale=3`), đo trực tiếp thời gian firing của 3 alerts, truy xuất `trace_id` và chụp 4 ảnh thật từ Grafana/Jaeger/Prometheus.
