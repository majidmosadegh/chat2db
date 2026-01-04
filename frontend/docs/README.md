# Frontend Development Documentation

این مستندات شامل تمام الگوها، استانداردها و راهنماهای توسعه frontend است.

## 📚 مستندات

### 1. [UI/UX Patterns](./UI_UX_PATTERNS.md) ⭐ **شروع از اینجا**
الگوهای اجباری برای توسعه UI/UX. **همه توسعه‌دهندگان و AI باید از این الگوها پیروی کنند.**

شامل:
- Component Structure
- Form Patterns
- Dialog Patterns
- Loading States
- Error Handling
- Validation Patterns
- Accessibility Requirements
- Keyboard Navigation
- Development Checklist

### 2. [Component Architecture](./COMPONENT_ARCHITECTURE.md)
ساختار و معماری کامپوننت‌ها، naming conventions، و best practices.

### 3. [Design System](../lib/design-system.ts)
ثابت‌های design system (spacing, typography, colors, etc.)

## 🚀 شروع سریع

### برای توسعه‌دهندگان جدید

1. **ابتدا این فایل را بخوان**: `UI_UX_PATTERNS.md`
2. **سپس**: `COMPONENT_ARCHITECTURE.md`
3. **مرجع**: `design-system.ts` برای constants

### برای AI Development

1. **همیشه ابتدا**: `UI_UX_PATTERNS.md` را بخوان
2. **سپس**: مثال‌های موجود را بررسی کن
3. **در نهایت**: از الگوها دقیقاً پیروی کن

## 📋 Quick Reference

### Form Pattern
```typescript
// State
const [formData, setFormData] = useState<FormData>({})
const [formErrors, setFormErrors] = useState<FormErrors>({})

// Validation
const validateForm = (): FormErrors => { /* ... */ }

// Submit
const handleSubmit = async (e?: React.FormEvent) => {
  e?.preventDefault()
  const errors = validateForm()
  if (Object.keys(errors).length > 0) {
    setFormErrors(errors)
    return
  }
  // API call
}

// JSX
<form onSubmit={handleSubmit}>
  <Input
    className={formErrors.field ? "border-destructive" : ""}
    onChange={(e) => {
      setFormData(prev => ({ ...prev, field: e.target.value }))
      if (formErrors.field) {
        setFormErrors(prev => ({ ...prev, field: undefined }))
      }
    }}
  />
  {formErrors.field && (
    <p className="text-sm text-destructive">{formErrors.field}</p>
  )}
</form>
```

### Dialog Pattern
```typescript
// State
const [showDialog, setShowDialog] = useState(false)
const [showDeleteDialog, setShowDeleteDialog] = useState(false)

// Delete
const handleDelete = (id: number) => {
  setItemToDelete(id)
  setShowDeleteDialog(true)
}

// JSX
<Dialog open={showDialog} onOpenChange={(open) => {
  setShowDialog(open)
  if (!open) {
    setFormData({})
    setFormErrors({})
  }
}}>
  {/* Content */}
</Dialog>

<ConfirmationDialog
  open={showDeleteDialog}
  onOpenChange={setShowDeleteDialog}
  title="Delete Item"
  description="Are you sure?"
  onConfirm={handleDeleteConfirm}
  variant="destructive"
/>
```

### Loading Pattern
```typescript
// Page-level
if (loading) {
  return <PageLoader message="Loading..." />
}

// Button-level
<Button disabled={loading}>
  {loading ? (
    <>
      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
      Saving...
    </>
  ) : (
    "Save"
  )}
</Button>
```

## ✅ Checklist قبل از Commit

- [ ] از `<form>` با `onSubmit` استفاده شده
- [ ] از `ConfirmationDialog` استفاده شده (نه `confirm()`)
- [ ] از `PageLoader` برای page-level loading
- [ ] Validation errors در state نگه داشته می‌شوند
- [ ] Field-level errors نمایش داده می‌شوند
- [ ] Icon-only buttons: `aria-label` + `title`
- [ ] Form labels: `Label` با `htmlFor`
- [ ] Enter key کار می‌کند
- [ ] Escape key کار می‌کند
- [ ] Error handling کامل است
- [ ] Loading states نمایش داده می‌شوند

## 🔗 لینک‌های مفید

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Radix UI](https://www.radix-ui.com)
- [shadcn/ui](https://ui.shadcn.com)

## 📝 مثال‌های موجود

برای دیدن الگوها در عمل، به این فایل‌ها مراجعه کن:

- `app/relationships/page.tsx` - Form + Dialog + Validation کامل
- `app/data-dictionary/page.tsx` - Edit Dialog Pattern
- `app/database/page.tsx` - Delete Confirmation Pattern

## ⚠️ مهم

**این الگوها اجباری هستند. هر کدی که از این الگوها پیروی نکند، باید refactor شود.**

**AI Development Rule**: هنگام توسعه هر feature جدید، ابتدا `UI_UX_PATTERNS.md` را بخوان و از الگوها دقیقاً پیروی کن.



