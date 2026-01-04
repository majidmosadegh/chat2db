# بهینه‌سازی Fast Intent Detection

## 🎯 مشکل

قبلاً برای مکالمات عادی (سلام، ممنون، کمک) هم کل پروسه اجرا می‌شد:
1. Context Loading (100-500ms) ❌
2. Conversation History Loading ❌
3. Reasoning Pipeline (2-5s) ❌
4. SQL Generation (حتی برای CONVERSATIONAL) ❌

**کل زمان: 3-7 ثانیه برای یک "سلام" ساده!**

## ✅ راه حل

### Fast Intent Detection با LLM

**قبل از Context Loading:**
1. یک LLM call سبک برای intent detection + response generation
2. اگر CONVERSATIONAL با confidence >= 0.7 → سریع برگردان
3. اگر DATA_QUERY → ادامه با context loading

**فایل:** `backend/chat/engine/fast_intent_detector.py`

## 🔄 فلو جدید

```
User Question
    ↓
Fast Intent Detection (LLM - ~500ms-1s)
    ↓
┌─────────────────┬─────────────────┐
│ CONVERSATIONAL  │   DATA_QUERY    │
│ (confidence≥0.7)│                 │
    ↓                    ↓
Return Response    Context Loading
(~1s total)        SQL Pipeline
                   (~3-7s total)
```

## 📊 بهبود Performance

### قبل:
- مکالمه عادی: **3-7s** (context + reasoning + SQL)
- سوال داده: **3-7s**

### بعد:
- مکالمه عادی: **0.5-1.5s** (فقط fast intent detection) ⚡
- سوال داده: **3-7s** (بدون تغییر)

**بهبود: 70-85% کاهش زمان برای مکالمات عادی**

## 🎯 ویژگی‌ها

1. **LLM-based**: از pattern matching استفاده نمی‌کند
2. **Immediate Response**: اگر conversational بود، همانجا response تولید می‌کند
3. **Lightweight**: فقط یک LLM call با max_tokens=200
4. **Smart Fallback**: اگر LLM fail شد، fallback response دارد

## 📝 مثال‌ها

### مکالمه عادی (Fast Path):
```
User: "سلام"
→ Fast Intent Detection (~500ms)
→ Detected: CONVERSATIONAL (confidence: 0.9)
→ Response: "سلام! من دستیار SQL شما هستم..."
→ Total: ~500ms ⚡
```

### سوال داده (Normal Path):
```
User: "قیمت قیر 6070 چقدر است؟"
→ Fast Intent Detection (~500ms)
→ Detected: DATA_QUERY (confidence: 0.9)
→ Context Loading (~100ms)
→ SQL Pipeline (~3-5s)
→ Total: ~3.5-5.5s
```

## 🔧 Configuration

```python
# backend/chat/engine/fast_intent_detector.py

# LLM call parameters
temperature=0.7  # برای پاسخ‌های طبیعی‌تر
max_tokens=200   # محدود برای سرعت

# Confidence threshold
confidence_threshold = 0.7  # اگر >= 0.7، skip context loading
```

## 📊 Logging

```
⚡ FAST_INTENT_START | Question: 'سلام' | Language: fa
✅ FAST_INTENT_COMPLETE | Intent: CONVERSATIONAL | Confidence: 0.90 | Time: 523ms
⚡ FAST_CONVERSATIONAL_RESPONSE | TotalTime: 523ms | Skipped: Context Loading, SQL Pipeline
```

## 🎯 مزایا

1. ✅ **سرعت بالا**: 70-85% کاهش زمان برای مکالمات
2. ✅ **هوشمند**: از LLM استفاده می‌کند (نه static patterns)
3. ✅ **انعطاف‌پذیر**: می‌تواند context را در نظر بگیرد
4. ✅ **مقیاس‌پذیر**: برای انواع سوالات کار می‌کند

## 🔍 Monitoring

برای monitoring effectiveness:

```python
# در logs دنبال کنید:
# - FAST_INTENT_START
# - FAST_INTENT_COMPLETE
# - FAST_CONVERSATIONAL_RESPONSE

# Metrics:
# - Fast detection time
# - Confidence scores
# - Skip rate (چند درصد skip می‌شوند)
```


