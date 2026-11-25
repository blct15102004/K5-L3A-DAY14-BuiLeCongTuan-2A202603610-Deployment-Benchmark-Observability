# Deployment Information

## Public URL
https://<your-agent-domain>.up.railway.app

> **Lưu ý:** Cần đăng nhập tài khoản Railway (`railway login`) hoặc Render Blueprint trên trình duyệt để xuất bản service từ thư mục `06-lab-complete/` kèm Redis add-on và cập nhật URL thực tế vào đây trước khi nộp bài.

## Platform
Railway (hoặc Render) — cấu hình sẵn trong `06-lab-complete/railway.toml` và `06-lab-complete/render.yaml`

## Deploy Commands (Railway)
```bash
cd 06-lab-complete
npm i -g @railway/cli
railway login
railway init
# Tạo thêm Redis service trên Railway Dashboard, sau đó set biến môi trường:
railway variables set AGENT_API_KEY=<your-secret-key>
railway variables set REDIS_URL='${{Redis.REDIS_URL}}'
railway up
railway domain
```

## Test Commands

### Health & Readiness Check
```bash
BASE="https://<your-agent-domain>.up.railway.app"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"   # Expected: 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"    # Expected: 200
```

### API Test (Authentication)
```bash
# Không có API key -> 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Có API key -> 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question": "Hello"}'
```

## Environment Variables Set
- `PORT` (do nền tảng tự cấp)
- `REDIS_URL` (trỏ tới Redis service trên Railway/Render)
- `AGENT_API_KEY` (đặt trên dashboard, không lưu trong code)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `MONTHLY_BUDGET_USD=10.0`
- `LOG_LEVEL=INFO`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
