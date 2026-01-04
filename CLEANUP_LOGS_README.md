# راهنمای پاک کردن لاگ‌های قدیمی از درایو C

## 📋 توضیحات

این اسکریپت‌ها برای پیدا کردن و پاک کردن لاگ‌های قدیمی loguru از درایو C ایجاد شده‌اند.

## 🔍 مرحله 1: پیدا کردن لاگ‌های قدیمی (بدون پاک کردن)

قبل از پاک کردن، ابتدا ببینید چه لاگ‌هایی وجود دارد:

### گزینه 1: استفاده از فایل batch (ساده‌ترین روش)
```batch
find_logs.bat
```

### گزینه 2: استفاده از PowerShell
```powershell
.\find_logs.bat
```

### گزینه 3: استفاده مستقیم از Python
```bash
cd backend
python scripts/cleanup_old_logs.py
```

## 🗑️ مرحله 2: پاک کردن لاگ‌های قدیمی

بعد از بررسی، می‌توانید لاگ‌ها را پاک کنید:

### گزینه 1: استفاده از فایل batch (ساده‌ترین روش)
```batch
cleanup_logs.bat
```

### گزینه 2: استفاده از PowerShell
```powershell
.\cleanup_logs.ps1
```

### گزینه 3: استفاده مستقیم از Python
```bash
cd backend
python scripts/cleanup_old_logs.py --delete
```

## 📍 مسیرهای معمول loguru در Windows

اسکریپت این مسیرها را بررسی می‌کند:

1. `%LOCALAPPDATA%\Loguru\` (معمولاً `C:\Users\<username>\AppData\Local\Loguru\`)
2. `%TEMP%\Loguru\`
3. `C:\Loguru\`
4. `C:\Windows\Loguru\`
5. `C:\ProgramData\Loguru\`

## ✅ بعد از پاک کردن

بعد از پاک کردن لاگ‌های قدیمی:
- همه لاگ‌های جدید در `backend/logs/` ذخیره می‌شوند
- دیگر درایو C پر نمی‌شود
- لاگ‌ها به صورت خودکار مدیریت می‌شوند (rotation و compression)

## ⚠️ هشدار

- قبل از پاک کردن، مطمئن شوید که لاگ‌های مهم را بکاپ گرفته‌اید
- اسکریپت فقط لاگ‌های loguru را پاک می‌کند
- لاگ‌های دیگر برنامه‌ها تحت تأثیر قرار نمی‌گیرند




