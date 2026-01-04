import requests
import json

url = 'http://localhost:8000/api/ai/dictionary/generate'
data = {
    'snapshot_id': 1,
    'business_domain': 'بازار سرمایه – بورس انرژی و بورس کالا (معاملات انرژی، کالاهای داخلی و صادراتی)',
    'database_description': 'این پایگاه داده نمایانگر اطلاعات معاملات، حراج‌ها، عرضه و تقاضا در بورس انرژی و بورس کالا است و از فرآیندهای زیر پشتیبانی می‌کند: ثبت داده‌های مربوط به معاملات انرژی و کالا، مدیریت اطلاعات قیمت، حجم، ارزش معاملات و شرایط قرارداد، ذخیره اطلاعات بازیگران بازار شامل تولیدکنندگان، عرضه‌کنندگان و کارگزاران، پشتیبانی از گزارش‌گیری، تحلیل بازار، پایش عملکرد معاملات و تصمیم‌سازی مدیریتی',
    'target_user': 'تحلیل‌گران کسب‌وکار و بازار سرمایه، تیم‌های تحلیل داده و هوش تجاری (BI)، واحدهای عملیات بازار و مدیریت معاملات، واحدهای نظارت، گزارش‌دهی و رگولاتوری',
    'language': 'persian'
}

print("Sending request to generate AI dictionary...")
print("Data:", json.dumps(data, ensure_ascii=False, indent=2))

response = requests.post(url, json=data)
print('\nStatus Code:', response.status_code)
print('Response:', json.dumps(response.json(), ensure_ascii=False, indent=2))
