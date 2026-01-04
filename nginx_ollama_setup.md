# راهنمای تنظیم Nginx برای Ollama

## مشکل فعلی
خطای 502 Bad Gateway معمولاً به این معنی است که nginx نمی‌تواند به Ollama backend وصل شود.

## مراحل نصب و تنظیم

### 1. بررسی وضعیت nginx
```bash
# بررسی اینکه nginx نصب است
nginx -v

# بررسی وضعیت سرویس
sudo systemctl status nginx

# بررسی اینکه nginx در حال listen کردن است
sudo netstat -tlnp | grep nginx
# یا
sudo ss -tlnp | grep nginx
```

### 2. ایجاد فایل تنظیمات
```bash
# کپی فایل تنظیمات
sudo cp nginx_ollama.conf /etc/nginx/sites-available/ollama

# ایجاد symlink
sudo ln -s /etc/nginx/sites-available/ollama /etc/nginx/sites-enabled/ollama

# یا اگر می‌خواهید مستقیماً در conf.d قرار دهید:
sudo cp nginx_ollama.conf /etc/nginx/conf.d/ollama.conf
```

### 3. تست تنظیمات
```bash
# تست syntax
sudo nginx -t

# اگر خطا داشت، بررسی کنید:
# - آیا پورت 11435 قبلاً استفاده شده؟
# - آیا مسیر فایل‌ها درست است؟
```

### 4. بررسی اتصال به Ollama
```bash
# از داخل سرور تست کنید
curl http://localhost:11434/api/tags

# اگر کار نکرد، بررسی کنید container در حال اجراست:
docker ps | grep ollama
```

### 5. Reload nginx
```bash
# Reload تنظیمات
sudo systemctl reload nginx

# یا restart کامل
sudo systemctl restart nginx
```

### 6. تست از خارج
```bash
# از یک ماشین دیگر
curl http://37.255.205.140:11435/api/tags
```

## مشکلات رایج و راه‌حل

### مشکل 1: پورت در حال استفاده است
```bash
# بررسی چه پروسه‌ای از پورت استفاده می‌کند
sudo lsof -i :11435
# یا
sudo netstat -tlnp | grep 11435

# اگر nginx قبلاً listen می‌کند، باید پورت را تغییر دهید
```

### مشکل 2: Ollama به localhost وصل نمی‌شود
```bash
# بررسی اینکه Ollama container در حال اجراست
docker ps | grep ollama

# بررسی پورت داخلی
docker port ollama-gpu

# تست مستقیم
curl http://localhost:11434/api/tags
```

### مشکل 3: SELinux یا AppArmor
```bash
# اگر SELinux فعال است
sudo setsebool -P httpd_can_network_connect 1

# بررسی log nginx
sudo tail -f /var/log/nginx/error.log
```

### مشکل 4: فایروال
```bash
# اگر UFW فعال است
sudo ufw allow 11435/tcp

# بررسی iptables
sudo iptables -L -n | grep 11435
```

## بررسی Log ها

```bash
# Log nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Log Ollama container
docker logs ollama-gpu
```

## تنظیمات پیشرفته

اگر می‌خواهید از HTTPS استفاده کنید، باید SSL certificate اضافه کنید:

```nginx
server {
    listen 11435 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    # ... rest of config
}
```

## تست نهایی

بعد از تنظیم، این تست‌ها را انجام دهید:

```bash
# 1. تست از داخل سرور
curl http://localhost:11435/api/tags

# 2. تست از خارج
curl http://37.255.205.140:11435/api/tags

# 3. تست generation
curl -X POST http://37.255.205.140:11435/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma3:4b","prompt":"Hello","stream":false}'
```

