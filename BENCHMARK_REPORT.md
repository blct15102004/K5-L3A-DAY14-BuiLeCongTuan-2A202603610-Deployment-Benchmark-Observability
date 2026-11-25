# Benchmark & Observability Report — Day 14

**Họ tên:** Bùi Lê Công Tuấn (MSSV: 2A202603610)  
**Ngày chạy:** 2026-11-25  
**Môi trường:** Windows 11 + Docker Desktop 29.9.3 (Compose v5.7.0), Python 3.11.6

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Đảm bảo 95% người dùng nhận phản hồi dưới 0,5 giây (trải nghiệm hội thoại mượt mà, phù hợp mặc định `load_test.py --slo-p95-ms 500`). |
| Error rate `/ask` | ≤ 2.0 % | Cho phép sai số nhỏ từ lỗi upstream ngẫu nhiên (`MOCK_ERROR_RATE=0.01`), nhưng bảo đảm độ tin cậy ≥ 98%. |
| Accuracy trên golden dataset | ≥ 85 % (mục tiêu 100%, 0 regression) | Ngăn bản phát hành mới trả lời kém hơn baseline trước khi merge/deploy (quality gate trong CI). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.17 | 197.5 | 236.5 | 1712.1 | 1.00% | ✅ PASS |
| 10 | 41.96 | 196.0 | 230.2 | 1689.2 | 1.67% | ✅ PASS |
| 50 | 110.96 | 196.5 | 250.7 | 362.6 | 1.33% | ✅ PASS |
| 100 | 58.51 | 624.4 | 4000.1 | 4603.6 | 0.67% | ❌ FAIL (p95 > 500 ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không tăng tuyến tính ở mức tải cao. Từ concurrency `1 → 10 → 50`, vì app dùng `async` non-blocking, RPS tăng gần tuyến tính (`4.17 → 41.96 → 110.96 req/s`) trong khi `p95` giữ ổn định quanh `230–251 ms`. Tuy nhiên tới concurrency `100`, hệ thống vượt điểm bão hòa (event loop / connection handling của 1 process `uvicorn` đơn lẻ bị nghẽn hàng đợi), khiến `p50` nhảy từ `196.5 ms` lên `624.4 ms`, `p95` vọt lên `4000.1 ms` (vi phạm SLO) và RPS tụt xuống còn `58.51 req/s`.

### 2.2 Tail latency (`--requests 300 --concurrency 20`)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 186.7 | 222.0 | 235.8 |
| 0.03 (mặc định) | 248.7 | 235.5 | 1694.7 |
| 0.1 | 310.0 | 1689.3 | 1714.2 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` và `p95` nhạy nhất với request chậm (tail latency). Khi `MOCK_SLOW_RATE` tăng từ `0` lên `0.03`, `avg` chỉ tăng nhẹ từ `186.7 ms` lên `248.7 ms` (+33%), nhưng `p99` tăng vọt hơn 7 lần từ `235.8 ms` lên `1694.7 ms`. Khi tăng tiếp lên `0.1`, `avg` vẫn ở mức `310.0 ms` (trông có vẻ dưới ngưỡng 500 ms), nhưng `p95` đã vọt lên `1689.3 ms` và làm **FAIL SLO**. Do đó không thể đặt SLO theo `average` vì trung bình cộng che giấu trải nghiệm rất tệ của nhóm người dùng gặp tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.0 | 109.0 | 113.7 |
| Tổng cost (USD) | $0.000403 | $0.000759 | $0.000790 |
| Cost / câu đúng (USD) | $0.00040275 | $0.00003616 | $0.00003436 |
| Quality gate | ❌ FAIL | ✅ PASS (ngưỡng 80%) | ✅ PASS (ngưỡng 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung entry `(["jwt"], ...)` giải thích JWT là token có chữ ký số và thời điểm hết hạn vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung entry `(["hpa", "kubernetes", "autoscal"], ...)` giải thích Kubernetes HPA scale dựa trên CPU, memory hoặc custom metrics vào `KNOWLEDGE_BASE`. |

**Quality gate CI (Exercise 7.3):** Đã tạo workflow [.github/workflows/eval.yml](.github/workflows/eval.yml) chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85`. Khi accuracy < 85% hoặc có regression so với baseline, `run_eval.py` thoát với exit code `1` nên GitHub Actions sẽ đánh fail job và chặn merge PR.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent `v2` (có bước retrieval/RAG) chèn thêm context vào prompt nên `avg_tokens` tăng gần gấp đôi (`57.0 → 113.7` tokens/câu) và `p50` latency tăng khoảng `+48 ms` (`153.0 → 200.9 ms`). Đổi lại, độ chính xác tăng vọt từ `4.3%` lên `100.0%`. Nếu xét theo chỉ số **cost / câu đúng**, `v2` (`$0.00003436`) rẻ hơn **gần 12 lần** so với `v1` (`$0.00040275`) vì `v1` tốn tiền cho rất nhiều câu trả lời sai.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

**Trả lời câu hỏi Exercise 7.4:**
1. **p95 và avg trên Grafana:** Trong các đợt tải chuẩn, `p50 ≈ 190 ms`, `p95 ≈ 220–230 ms`, còn `p99` nhảy lên `~1.7–1.98 s`. Khoảng cách lớn giữa `avg/p95` và `p99` phản ánh rõ tail latency (~3% request chậm thêm 1.5s).
2. **Nginx load balancing:** Có — Nginx phân tán request qua cả 3 container agent theo round-robin; panel *Instances* hiển thị đủ `3` instance khỏe mạnh.
3. **Input tokens/s lớn hơn output tokens/s:** Vì mỗi request `v2` gửi kèm `SYSTEM_PROMPT` + tài liệu retrieve được từ `KNOWLEDGE_BASE` + câu hỏi của người dùng làm input, trong khi câu trả lời đầu ra ngắn gọn hơn.
4. **`curl -i http://localhost:8080/metrics`:** Trả về **`404 Not Found`** từ Nginx vì `nginx.conf` cố tình chặn không public `/metrics` ra Internet (chỉ cho phép Prometheus scrape nội bộ qua mạng Docker), tránh lộ thông tin vận hành hệ thống.

### 4.2 Thí nghiệm "phá hệ thống"

Đã kiểm thử unit test rule bằng `promtool test rules /p/alert_rules_test.yml` (`SUCCESS`) và chạy thực nghiệm kết hợp fault injection (`MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3`, `docker pause k5-day14-observability-agent-3`) dưới tải Locust 30 users, ghi nhận **cả 3 alert cùng chuyển sang trạng thái `firing`**:

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`for: 1m`) | **70.2 s** (pending ở 10.0s) | Error rate & Requests/s theo status code (503) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`for: 2m`) | **130.3 s** (pending ở 15.0s) | Latency /ask — p50 / p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` *(chưa chạy riêng)* | *(Kỳ vọng: `LLMCostBurnRateHigh`)* | *(for: 2m)* | Cost burn rate (USD/giờ) |
| D | `docker pause k5-day14-observability-agent-3` | `AgentInstanceDown` (`for: 30s`) | **45.1 s** (pending ở 15.0s) | Instances (giảm từ 3 xuống 2) |
| E | `AGENT_VERSION=v1` *(chưa chạy riêng trên stack)* | Không có alert nào firing | N/A | Retrieval hit ratio & bảng version |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Các alert hạ tầng (CPU, HTTP 5xx, latency) chỉ đo được *hệ thống có chạy và phản hồi nhanh không*, không đo được *chất lượng câu trả lời*. Để phát hiện suy giảm chất lượng trên production cần: (1) chạy **eval CI quality gate** trên golden dataset trước mỗi lần deploy, (2) theo dõi các **business/RAG metrics** như `retrieval_hit_ratio` (tụt về 0 khi chạy `v1`), token/output length, (3) thiết lập **online eval / LLM-as-judge** lấy mẫu traffic thật và thu thập phản hồi người dùng (thumbs up/down).

### 4.3 Debug bằng trace

**Trace chậm nhất đã chọn:**
- `trace_id`: `e2d9ddd915dc23ff4f6113730354ea6b`
- Tổng thời gian: **1700 ms** (`1.7s` trên Jaeger; riêng bước `llm_ms` = `1698.8 ms`)
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small`** (`1.7s` / `1698.8 ms`, chiếm **~98.8%** tổng thời gian request; trong khi `agent.retrieve_context` chỉ mất `20.3 ms`)
- Dòng log tương ứng (lọc theo `trace_id` từ `docker compose -p k5-day14-observability logs agent`):

```json
{"ts": "2026-11-25T08:08:11.150833+00:00", "level": "INFO", "service": "observable-agent", "instance": "c83544a67f6e", "event": "llm_call", "trace_id": "e2d9ddd915dc23ff4f6113730354ea6b", "span_id": "2bb8a17f26698d94", "request_id": "aa91b4343456", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1698.8}
```

**Trace lỗi đã đối chiếu (`jaeger-error-trace.png`):**
- `trace_id`: `f42056fb45d172daedb86052dfc88b14`
- Dòng log tương ứng:

```json
{"ts": "2026-11-25T08:07:10.269266+00:00", "level": "INFO", "service": "observable-agent", "instance": "c83544a67f6e", "event": "llm_error", "trace_id": "f42056fb45d172daedb86052dfc88b14", "span_id": "9295f0de8f7e5d9a", "request_id": "f78489b85209", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu `POST /ask` trích trực tiếp từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`:

| Số instance | RPS (`/ask` / Tổng) | p50 (ms) | p95 (ms) | p99 (ms) | Failures (`/ask` / Tổng) |
|---|---|---|---|---|---|
| 1 | 59.67 / 65.57 | 190 | 230 | 1700 | 64 (0.90%) / 64 (0.82%) |
| 3 | 60.03 / 66.02 | 190 | 220 | 1700 | 72 (1.00%) / 72 (0.91%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Scale từ 1 lên 3 instance chỉ giảm nhẹ `p95` của `/ask` từ `230 ms` xuống `220 ms`, còn `p50` (`190 ms`), `p99` (`1700 ms`) và throughput (`~66 req/s`) gần như giữ nguyên. Có hai nguyên nhân:
1. **Nút thắt nằm ở độ trễ gọi LLM upstream** (`chat mock-llm-small` mất ~190 ms cho request thường và ~1700 ms cho tail latency, có thể thấy trực tiếp trong Jaeger). Vì xử lý của agent dùng `asyncio` I/O-bound nên 1 instance đã gánh tốt 100 concurrent users mà chưa chạm ngưỡng CPU; thêm instance không rút ngắn được thời gian chờ LLM trả về.
2. **Tải sinh từ Locust có `wait_time` cố định theo 100 users**, nên tổng tốc độ gửi request từ phía client bị chặn quanh ~66 req/s ở cả hai lần chạy.

---

## 6. Kết luận

- **3 điều học được về benchmark & observability:**
  1. Không bao giờ đánh giá hiệu năng bằng `average` hay `eval` 23 câu — phải dùng **load test** và đặt **SLO theo `p95`/`p99`** để phát hiện tail latency.
  2. **Chất lượng không tách rời chi phí:** chỉ số `cost / câu đúng` phản ánh đúng giá trị của kiến trúc RAG (`v2` đắt token hơn mỗi lượt nhưng rẻ hơn ~12 lần cho mỗi câu trả lời đúng).
  3. **Metrics – Traces – Logs bổ trợ cho nhau:** Grafana báo triệu chứng (p95/error tăng), Jaeger chỉ ra span gây nghẽn/lỗi (`chat mock-llm-small`), còn `trace_id` giúp truy thẳng tới dòng log JSON gốc để debug.
- **Nếu đưa agent này lên production thật, sẽ thêm metric / alert:**
  - Metric & alert cho **RAG retrieval quality / hit ratio** và **empty/fallback answer rate** (phát hiện suy giảm chất lượng như thí nghiệm E).
  - Metric cho **rate limit rejections (`429`)** và **budget exceeded (`402`)**, cùng cảnh báo **budget burn rate theo ngày** qua Slack/PagerDuty (Alertmanager).
  - **Synthetic probe từ bên ngoài** (blackbox exporter) để bắt các lỗi ở tầng Nginx/gateway (502/504) mà metric nội bộ của agent không nhìn thấy.
