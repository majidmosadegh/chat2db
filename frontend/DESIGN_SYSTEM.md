# Design System Documentation

این سند راهنمای استفاده از سیستم طراحی پروژه است.

## 🎨 فلسفه طراحی

سیستم طراحی ما بر پایه اصول زیر بنا شده:
- **Consistency**: یکپارچگی در تمامی کامپوننت‌ها
- **Accessibility**: دسترسی‌پذیری برای همه کاربران
- **Performance**: بهینه‌سازی برای عملکرد بهتر
- **Maintainability**: قابلیت نگهداری آسان

## 🏗️ ساختار

```
frontend/
├── components/
│   ├── ui/                 # کامپوننت‌های پایه قابل استفاده مجدد
│   └── [feature]/          # کامپوننت‌های مخصوص ویژگی‌ها
├── lib/
│   ├── design-system.ts    # ابزارهای طراحی
│   ├── theme-provider.tsx # مدیریت تم
│   └── utils.ts           # ابزارهای کمکی
└── DESIGN_SYSTEM.md       # این فایل
```

## 🎯 کامپوننت‌های پایه

### Button
```tsx
import { Button } from "@/components/ui/button"

// Variants
<Button variant="default">Default</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
```

### Card
```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
  </CardHeader>
  <CardContent>
    Card content
  </CardContent>
</Card>
```

### Loading States
```tsx
import { Skeleton, PageLoader, CardSkeleton } from "@/components/ui/loading"

// Page loader
<PageLoader message="Loading data..." />

// Skeleton for cards
<CardSkeleton />
```

### Empty States
```tsx
import { EnhancedEmptyState, NoDataState } from "@/components/ui/enhanced-empty-state"

// Enhanced empty state
<EnhancedEmptyState
  title="No data found"
  description="Try refreshing the page"
  actions={{
    primary: { label: "Refresh", onClick: handleRefresh }
  }}
/>

// Specialized empty state
<NoDataState onRefresh={handleRefresh} />
```

## 🎭 تم‌ها و رنگ‌ها

### Theme Provider
```tsx
import { ThemeProvider } from "@/lib/theme-provider"

// Wrap your app
<ThemeProvider
  attribute="class"
  defaultTheme="system"
  enableSystem
>
  <App />
</ThemeProvider>
```

### Theme Toggle
```tsx
import { ThemeToggle } from "@/components/ui/theme-toggle"

<ThemeToggle />
```

## 📐 Spacing & Typography

### Spacing Scale
```tsx
import { spacing } from "@/lib/design-system"

// استفاده در کلاس‌ها
className={`p-${spacing[4]} m-${spacing[2]}`}
```

### Typography Scale
```tsx
import { typography } from "@/lib/design-system"

// Font sizes
className={`text-${typography.lg}`}

// Font weights
className={`font-${typography.semibold}`}
```

## ✨ انیمیشن‌ها

### Page Transitions
```tsx
import { PageTransition } from "@/components/ui/page-transition"

<PageTransition>
  <YourPageContent />
</PageTransition>
```

### Toast Notifications
```tsx
import { useToast } from "@/components/ui/toast-notification"

const { success, error, warning, info } = useToast()

// استفاده
success("Operation successful!", "Data saved successfully")
error("Error occurred", "Please try again")
```

## 📱 Responsive Design

### Breakpoints
```tsx
// در tailwind.config.js تعریف شده
{
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1536px"
}
```

### Responsive Utilities
```tsx
import { createResponsiveClass } from "@/lib/design-system"

// ایجاد کلاس responsive
const responsiveClass = createResponsiveClass(
  "text-sm",      // base
  "md:text-base", // medium screens
  "lg:text-lg"    // large screens
)
```

## 🔧 ابزارهای کمکی

### CN Utility
```tsx
import { cn } from "@/lib/utils"

// ترکیب کلاس‌ها
className={cn(
  "base-class",
  condition && "conditional-class",
  variant === "primary" && "primary-class"
)}
```

## 📋 چک لیست توسعه کامپوننت جدید

### ✅ قبل از اضافه کردن کامپوننت جدید:
- [ ] آیا کامپوننت پایه موجود قابل استفاده است؟
- [ ] آیا از design tokens استفاده کرده‌اید؟
- [ ] آیا کامپوننت responsive است؟
- [ ] آیا از TypeScript استفاده کرده‌اید؟
- [ ] آیا کامپوننت accessible است؟
- [ ] آیا کامپوننت با dark mode سازگار است؟
- [ ] آیا انیمیشن‌های مناسب اضافه کرده‌اید؟
- [ ] آیا کامپوننت تست شده است؟

### ✅ برای کامپوننت‌های پیچیده:
- [ ] آیا از composition pattern استفاده کرده‌اید؟
- [ ] آیا error boundaries اضافه کرده‌اید؟
- [ ] آیا loading states اضافه کرده‌اید؟
- [ ] آیا empty states اضافه کرده‌اید؟
- [ ] آیا کامپوننت به خوبی مستندسازی شده است؟

## 🚀 بهترین روش‌ها

### 1. استفاده از Design Tokens
```tsx
// ✅ خوب
import { spacing, colors } from "@/lib/design-system"
className={`p-${spacing[4]} ${colors.status.success.bg}`}

// ❌ بد
className="p-4 bg-green-50 dark:bg-green-950"
```

### 2. Responsive First
```tsx
// ✅ خوب
className="text-sm md:text-base lg:text-lg"

// ❌ بد
className="text-sm"
```

### 3. Accessibility
```tsx
// ✅ خوب
<Button aria-label="Save changes">Save</Button>

// ❌ بد
<button>Save</button>
```

### 4. Performance
```tsx
// ✅ خوب
const MemoizedComponent = memo(Component)

// ❌ بد
function Component() { /* بدون memo */ }
```

## 🔄 به‌روزرسانی سیستم طراحی

### اضافه کردن رنگ جدید:
1. رنگ را به `globals.css` اضافه کنید
2. در `design-system.ts` مستندسازی کنید
3. در کامپوننت‌های مربوطه استفاده کنید

### اضافه کردن کامپوننت جدید:
1. در `components/ui/` قرار دهید
2. از shadcn/ui patterns پیروی کنید
3. در این سند مستندسازی کنید
4. تست‌های لازم اضافه کنید

## 📚 منابع بیشتر

- [shadcn/ui Documentation](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Radix UI](https://www.radix-ui.com/)
- [Next.js Themes](https://github.com/pacocoursey/next-themes)














