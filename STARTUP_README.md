# راه‌اندازی SQL PT

## 🚀 راه‌اندازی سریع

برای راه‌اندازی کامل پروژه (Backend + Frontend)، فقط فایل زیر را اجرا کنید:

```bash
start.bat
```

این فایل به صورت خودکار:
- ✅ پورت‌های 8000 و 3000 را پاک می‌کند
- ✅ محیط مجازی Python را ایجاد/فعال می‌کند
- ✅ وابستگی‌های Backend را نصب می‌کند
- ✅ Backend را روی پورت 8000 راه‌اندازی می‌کند
- ✅ وابستگی‌های Frontend را نصب می‌کند
- ✅ Frontend را روی پورت 3000 راه‌اندازی می‌کند

## 📍 آدرس‌های سرویس

بعد از راه‌اندازی:
- **Backend API**: http://localhost:8000
- **Frontend App**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs

## 🛑 توقف سرویس‌ها

برای توقف سرویس‌ها، پنجره‌های CMD که باز شده‌اند را ببندید یا `Ctrl+C` بزنید.

## 📁 ساختار فایل‌ها

### فایل‌های تست
همه فایل‌های تست در `backend/tests/` سازمان‌دهی شده‌اند:
- `backend/tests/db/` - تست‌های دیتابیس
- `backend/tests/llm/` - تست‌های LLM
- `backend/tests/chat/` - تست‌های Chat Engine
- `backend/tests/dictionary/` - تست‌های Dictionary Generation
- `backend/tests/api/` - تست‌های API
- `backend/tests/services/` - تست‌های Services

### فایل‌های ابزار
فایل‌های utility/check/fix در `backend/scripts/utilities/` قرار دارند.

## 🔧 عیب‌یابی

اگر مشکلی پیش آمد:
1. مطمئن شوید Python و Node.js نصب هستند
2. پورت‌های 8000 و 3000 آزاد باشند
3. لاگ‌ها را در پنجره‌های CMD بررسی کنید

