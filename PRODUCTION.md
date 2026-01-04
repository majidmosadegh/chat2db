# Production Scripts Guide

## Start Production

برای راه‌اندازی محیط production از script زیر استفاده کنید:

```powershell
.\start-production.ps1
```

این script به صورت خودکار:
1. تمام پروسه‌های استفاده‌کننده از پورت‌های 8000 (backend) و 3000 (frontend) را متوقف می‌کند
2. سرور backend را راه‌اندازی می‌کند
3. سرور frontend را راه‌اندازی می‌کند
4. وضعیت هر دو سرور را بررسی می‌کند

### خروجی مورد انتظار:
```
========================================
Starting Production Environment
========================================
[1/4] Clearing backend port (8000)...
[2/4] Clearing frontend port (3000)...
[3/4] Starting backend server...
✓ Backend server is running on port 8000
[4/4] Starting frontend server...
✓ Frontend server is running on port 3000
========================================
Production Environment Status
========================================
Backend:  http://localhost:8000
Frontend: http://localhost:3000
========================================
```

## Stop Production

برای متوقف کردن تمام سرورها:

```powershell
.\stop-production.ps1
```

این script تمام پروسه‌های backend و frontend را متوقف می‌کند.

## دسترسی

بعد از راه‌اندازی:
- **Backend API**: http://localhost:8000
- **Frontend UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## نکات

- اگر پورت‌ها قبلاً استفاده شده باشند، script به صورت خودکار آنها را آزاد می‌کند
- اگر سرورها به درستی start نشوند، script پیام خطا نمایش می‌دهد
- برای بررسی لاگ‌ها، به `backend/logs/` مراجعه کنید

