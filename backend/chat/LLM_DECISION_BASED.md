# تصمیم‌گیری مبتنی بر LLM (LLM-Based Decision Making)

## 🎯 فلسفه طراحی

**همه تصمیمات توسط مدل گرفته می‌شود، نه کد استاتیک.**

### اصول:
1. ✅ **هیچ Pattern Matching استاتیک**: همه تصمیمات از LLM می‌آید
2. ✅ **Fallback با LLM**: اگر یک LLM call fail شد، یک LLM call دیگر می‌زنیم
3. ✅ **مدل تصمیم می‌گیرد**: مدل تشخیص می‌دهد conversational است یا data query
4. ✅ **مدل پاسخ می‌دهد**: مدل خودش پاسخ را تولید می‌کند

---

## 🔄 فلو تصمیم‌گیری

```
User Question
    ↓
Fast Intent Detection (LLM Call #1)
    ↓
┌─────────────────┬─────────────────┐
│ Success         │ Fail/Parse Error│
    ↓                    ↓
Parse JSON         Retry with Simple Prompt (LLM Call #2)
    ↓                    ↓
┌─────────┐        ┌──────────────┐
│ Success │        │ Fail Again   │
    ↓                    ↓
Check Intent        Last Resort (LLM Call #3)
    ↓                    ↓
┌─────────────────┬─────────────────┐
│ CONVERSATIONAL  │   DATA_QUERY    │
│ (confidence≥0.7)│   or Unknown    │
    ↓                    ↓
Generate Response   Continue to Normal Pipeline
(LLM Call if needed)    (Context + SQL)
    ↓
Return Fast
```

---

## 📝 مراحل LLM Calls

### 1. Primary LLM Call
**هدف:** Intent detection + Response generation (در یک call)

```python
prompt = """
شما یک دستیار هوشمند هستید. سوال کاربر را تحلیل کنید.

اگر مکالمه عادی: {"intent": "CONVERSATIONAL", "response": "...", "confidence": 0.9}
اگر سوال داده: {"intent": "DATA_QUERY", "confidence": 0.9}
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Retry با prompt ساده‌تر

---

### 2. Retry LLM Call (اگر #1 fail شد)
**هدف:** Intent detection با prompt ساده‌تر

```python
prompt = """
سوال: {question}

آیا مکالمه عادی است یا سوال داده؟
{"intent": "...", "response": "...", "confidence": 0.8}
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Last Resort

---

### 3. Last Resort LLM Call (اگر #2 fail شد)
**هدف:** پاسخ مستقیم بدون JSON parsing

```python
prompt = """
سوال: {question}

اگر مکالمه عادی: پاسخ دوستانه بنویس
اگر سوال داده: فقط بنویس "DATA_QUERY"
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Normal Pipeline (context loading + SQL)

---

### 4. Quick Response Generation (اگر intent داشتیم اما response نداشتیم)
**هدف:** تولید پاسخ برای conversational queries

```python
prompt = """
سوال: {question}

پاسخ دوستانه و مفید (حداکثر 2 جمله)
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Retry با prompt ساده‌تر

---

### 5. Simple Response (اگر #4 fail شد)
**هدف:** پاسخ ساده با minimal prompt

```python
prompt = """
سوال: {question}

پاسخ کوتاه:
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Absolute Last Resort

---

### 6. Absolute Last Resort (اگر همه fail شدند)
**هدف:** یک تلاش نهایی با minimal prompt

```python
prompt = """
سوال: {question}

پاسخ کوتاه:
"""
```

**اگر موفق شد:** ✅ استفاده می‌کنیم
**اگر fail شد:** → Normal Pipeline

---

## 🚫 چیزهایی که انجام نمی‌دهیم

### ❌ Pattern Matching
```python
# این کار را نمی‌کنیم:
if "سلام" in question:
    return "سلام! ..."
```

### ❌ Static Keywords
```python
# این کار را نمی‌کنیم:
conversational_words = ["hi", "hello", ...]
if any(word in question for word in conversational_words):
    return predefined_response
```

### ❌ Hardcoded Responses
```python
# این کار را نمی‌کنیم:
def get_fallback_response(question):
    if "thanks" in question:
        return "You're welcome!"
```

---

## ✅ چیزهایی که انجام می‌دهیم

### ✅ LLM-Based Detection
```python
# مدل تصمیم می‌گیرد:
result = await llm_gateway.call_llm(
    prompt="آیا این مکالمه عادی است یا سوال داده؟"
)
```

### ✅ LLM-Based Response Generation
```python
# مدل پاسخ تولید می‌کند:
response = await llm_gateway.call_llm(
    prompt="به این سوال پاسخ دوستانه بده: {question}"
)
```

### ✅ Multiple LLM Retries
```python
# اگر fail شد، دوباره با prompt دیگر:
try:
    result = await llm_call_1()
except:
    result = await llm_call_2()  # Different prompt
```

---

## 📊 مزایا

1. **هوشمند**: مدل می‌تواند context را درک کند
2. **انعطاف‌پذیر**: برای انواع سوالات کار می‌کند
3. **طبیعی**: پاسخ‌ها طبیعی‌تر هستند
4. **قابل یادگیری**: مدل می‌تواند از conversation history یاد بگیرد

---

## ⚠️ Trade-offs

### مزایا:
- ✅ پاسخ‌های طبیعی‌تر
- ✅ درک بهتر context
- ✅ انعطاف‌پذیری بیشتر

### معایب:
- ⚠️ کمی کندتر از pattern matching (اما هنوز سریع‌تر از full pipeline)
- ⚠️ نیاز به LLM call (اما lightweight است)

---

## 🎯 نتیجه

**همه تصمیمات توسط مدل گرفته می‌شود:**
- ✅ Intent detection: مدل
- ✅ Response generation: مدل
- ✅ Fallback handling: مدل (با retry)
- ✅ Error recovery: مدل (با simpler prompts)

**کد فقط orchestration می‌کند، تصمیم‌گیری نمی‌کند.**


