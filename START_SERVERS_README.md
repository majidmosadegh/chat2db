# راه‌اندازی سرورها

## فایل‌های راه‌اندازی

### 1. `start-backend-only.bat`
- فقط backend را روی پورت 8000 راه‌اندازی می‌کند
- سرور در همان پنجره اجرا می‌شود
- برای تست API مناسب است

### 2. `start-production-simple.bat`
- backend روی پورت 8000 و frontend روی پورت 3000 راه‌اندازی می‌کند
- هر کدام در پنجره جداگانه اجرا می‌شود
- برای توسعه مناسب است

### 3. `start-production.bat` (اصلی)
- فایل کامل برای production
- هر دو سرور را راه‌اندازی می‌کند
- cleanup کامل انجام می‌دهد

## استفاده

### Backend Only:
```
./start-backend-only.bat
```

### Full Production:
```
./start-production-simple.bat
```

یا

```
./start-production.bat
```

## آدرس‌ها

- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend UI: http://localhost:3000









