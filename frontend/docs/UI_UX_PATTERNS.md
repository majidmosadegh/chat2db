# UI/UX Development Patterns & Guidelines

این سند الگوها و استانداردهای توسعه UI/UX را تعریف می‌کند. **همه توسعه‌دهندگان و AI باید از این الگوها پیروی کنند.**

## 📋 فهرست مطالب

1. [Component Structure](#component-structure)
2. [Form Patterns](#form-patterns)
3. [Dialog Patterns](#dialog-patterns)
4. [Loading States](#loading-states)
5. [Error Handling](#error-handling)
6. [Validation Patterns](#validation-patterns)
7. [Accessibility Requirements](#accessibility-requirements)
8. [Keyboard Navigation](#keyboard-navigation)

---

## Component Structure

### استاندارد ساختار کامپوننت

```typescript
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/lib/use-toast"
import { PageLoader } from "@/components/ui/loading"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

// ✅ DO: Interface definitions at top
interface ComponentProps {
  // Props definition
}

interface FormData {
  // Form state structure
}

interface FormErrors {
  // Validation errors structure
  [key: string]: string | undefined
}

// ✅ DO: Main component
export default function ComponentName() {
  // 1. Hooks
  const { toast } = useToast()
  
  // 2. State - Group by purpose
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState<FormData>({})
  const [formErrors, setFormErrors] = useState<FormErrors>({})
  const [showDialog, setShowDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<number | null>(null)
  
  // 3. Effects
  useEffect(() => {
    // Side effects
  }, [])
  
  // 4. Handlers - Group by action type
  const handleSubmit = async () => {
    // Validation
    const errors = validateForm()
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }
    
    // API call
    try {
      setLoading(true)
      // ... API call
      toast({ title: "Success", description: "Operation successful" })
    } catch (error) {
      toast({ title: "Error", description: "Operation failed", variant: "destructive" })
    } finally {
      setLoading(false)
    }
  }
  
  const handleDelete = (id: number) => {
    setItemToDelete(id)
    setShowDeleteDialog(true)
  }
  
  const handleDeleteConfirm = async () => {
    // Delete logic
  }
  
  // 5. Render
  if (loading) {
    return <PageLoader message="Loading..." />
  }
  
  return (
    <div className="space-y-6">
      {/* Content */}
      
      <ConfirmationDialog
        open={showDeleteDialog}
        onOpenChange={(open) => {
          setShowDeleteDialog(open)
          if (!open) setItemToDelete(null)
        }}
        title="Delete Item"
        description="Are you sure?"
        onConfirm={handleDeleteConfirm}
        variant="destructive"
      />
    </div>
  )
}
```

### قوانین ساختار

1. **Import Order**: 
   - React hooks
   - UI components (from @/components/ui)
   - Custom components
   - Utilities & hooks
   - Types (if separate file)

2. **State Organization**:
   - Loading states first
   - Form/data states
   - UI states (dialogs, modals)
   - Error states

3. **Handler Organization**:
   - Submit handlers
   - Delete handlers
   - Edit handlers
   - UI handlers (open/close dialogs)

---

## Form Patterns

### ✅ استاندارد Form Structure

```typescript
// 1. Form state
const [formData, setFormData] = useState<FormData>({
  field1: "",
  field2: "",
})

// 2. Validation errors state
const [formErrors, setFormErrors] = useState<FormErrors>({})

// 3. Validation function
const validateForm = (): FormErrors => {
  const errors: FormErrors = {}
  
  if (!formData.field1.trim()) {
    errors.field1 = "Field 1 is required"
  }
  
  if (!formData.field2.trim()) {
    errors.field2 = "Field 2 is required"
  }
  
  return errors
}

// 4. Submit handler
const handleSubmit = async (e?: React.FormEvent) => {
  e?.preventDefault()
  
  const errors = validateForm()
  if (Object.keys(errors).length > 0) {
    setFormErrors(errors)
    toast({
      title: "Validation Error",
      description: "Please fill in all required fields",
      variant: "destructive"
    })
    return
  }
  
  setFormErrors({})
  
  try {
    setLoading(true)
    // API call
    toast({ title: "Success", description: "Saved successfully" })
  } catch (error) {
    toast({ title: "Error", description: "Failed to save", variant: "destructive" })
  } finally {
    setLoading(false)
  }
}

// 5. Form JSX with validation
<form onSubmit={handleSubmit} className="space-y-4">
  <div className="space-y-2">
    <Label htmlFor="field1">Field 1 *</Label>
    <Input
      id="field1"
      value={formData.field1}
      onChange={(e) => {
        setFormData(prev => ({ ...prev, field1: e.target.value }))
        if (formErrors.field1) {
          setFormErrors(prev => ({ ...prev, field1: undefined }))
        }
      }}
      className={formErrors.field1 ? "border-destructive" : ""}
    />
    {formErrors.field1 && (
      <p className="text-sm text-destructive">{formErrors.field1}</p>
    )}
  </div>
  
  <DialogFooter>
    <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
      Cancel
    </Button>
    <Button type="submit" disabled={loading}>
      {loading ? (
        <>
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          Saving...
        </>
      ) : (
        "Save"
      )}
    </Button>
  </DialogFooter>
</form>
```

### قوانین Form

1. **همیشه از `<form>` استفاده کن** - برای Enter key support
2. **Validation errors را در state نگه دار** - نه فقط toast
3. **Field-level errors نمایش بده** - زیر هر فیلد
4. **Border قرمز برای invalid fields** - `className={formErrors.field ? "border-destructive" : ""}`
5. **Clear errors on change** - وقتی کاربر تایپ می‌کند
6. **Enter key support** - با `onSubmit` در form
7. **Loading state در button** - نمایش spinner

---

## Dialog Patterns

### ✅ استاندارد Dialog Structure

```typescript
// 1. Dialog state
const [showDialog, setShowDialog] = useState(false)
const [showDeleteDialog, setShowDeleteDialog] = useState(false)
const [itemToDelete, setItemToDelete] = useState<number | null>(null)

// 2. Dialog handlers
const handleOpenDialog = () => {
  setFormData({}) // Reset form
  setFormErrors({}) // Clear errors
  setShowDialog(true)
}

const handleCloseDialog = () => {
  setShowDialog(false)
  setFormData({})
  setFormErrors({})
}

// 3. Delete confirmation pattern
const handleDelete = (id: number) => {
  setItemToDelete(id)
  setShowDeleteDialog(true)
}

const handleDeleteConfirm = async () => {
  if (!itemToDelete) return
  
  try {
    // Delete API call
    toast({ title: "Success", description: "Deleted successfully" })
  } catch (error) {
    toast({ title: "Error", description: "Failed to delete", variant: "destructive" })
  } finally {
    setShowDeleteDialog(false)
    setItemToDelete(null)
  }
}

// 4. Dialog JSX
<Dialog open={showDialog} onOpenChange={(open) => {
  setShowDialog(open)
  if (!open) {
    setFormData({})
    setFormErrors({})
  }
}}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Dialog Title</DialogTitle>
      <DialogDescription>Dialog description</DialogDescription>
    </DialogHeader>
    
    {/* Form content */}
    
    <DialogFooter>
      <Button type="button" variant="outline" onClick={handleCloseDialog}>
        Cancel
      </Button>
      <Button type="submit" onClick={handleSubmit}>
        Save
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>

{/* Delete Confirmation - ALWAYS use ConfirmationDialog, NEVER confirm() */}
<ConfirmationDialog
  open={showDeleteDialog}
  onOpenChange={(open) => {
    setShowDeleteDialog(open)
    if (!open) setItemToDelete(null)
  }}
  title="Delete Item"
  description="Are you sure you want to delete this item? This action cannot be undone."
  onConfirm={handleDeleteConfirm}
  confirmText="Delete"
  cancelText="Cancel"
  variant="destructive"
/>
```

### قوانین Dialog

1. **❌ NEVER use `confirm()`** - همیشه از `ConfirmationDialog` استفاده کن
2. **Reset state on close** - وقتی dialog بسته می‌شود
3. **Clear errors on close** - validation errors را پاک کن
4. **Escape key support** - Radix UI به صورت خودکار دارد
5. **Focus management** - Radix UI به صورت خودکار دارد
6. **Button types** - `type="button"` برای Cancel، `type="submit"` برای Save

---

## Loading States

### ✅ استاندارد Loading Patterns

```typescript
// 1. Page-level loading
if (loading) {
  return <PageLoader message="Loading data..." />
}

// 2. Button-level loading
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

// 3. Inline loading
{isGenerating && (
  <div className="flex items-center gap-2">
    <Loader2 className="h-4 w-4 animate-spin" />
    <span>Generating...</span>
  </div>
)}
```

### قوانین Loading

1. **Page-level**: از `PageLoader` استفاده کن
2. **Button-level**: از `Loader2` با `animate-spin` استفاده کن
3. **همیشه message نمایش بده** - "Loading...", "Saving...", etc.
4. **Disabled state** - دکمه‌ها را disable کن در حین loading

---

## Error Handling

### ✅ استاندارد Error Patterns

```typescript
// 1. API error handling
try {
  const response = await fetch("/api/endpoint")
  
  if (!response.ok) {
    const errorData = await response.json()
    const errorMessage = errorData.detail || errorData.message || "Operation failed"
    
    toast({
      title: "Error",
      description: errorMessage,
      variant: "destructive"
    })
    return
  }
  
  const data = await response.json()
  toast({
    title: "Success",
    description: "Operation completed successfully"
  })
} catch (error) {
  const errorMessage = error instanceof Error 
    ? error.message 
    : "An unexpected error occurred"
  
  toast({
    title: "Error",
    description: errorMessage,
    variant: "destructive"
  })
}
```

### قوانین Error Handling

1. **User-friendly messages** - پیام‌های واضح و قابل فهم
2. **Toast notifications** - برای همه errors
3. **Field-level errors** - برای validation
4. **Error recovery** - راه حل یا action پیشنهاد بده

---

## Validation Patterns

### ✅ استاندارد Validation

```typescript
// 1. Validation errors type
interface FormErrors {
  [key: string]: string | undefined
}

// 2. Validation function
const validateForm = (): FormErrors => {
  const errors: FormErrors = {}
  
  if (!formData.field1?.trim()) {
    errors.field1 = "Field 1 is required"
  }
  
  if (formData.field2 && formData.field2.length < 3) {
    errors.field2 = "Field 2 must be at least 3 characters"
  }
  
  return errors
}

// 3. Clear error on change
<Input
  value={formData.field1}
  onChange={(e) => {
    setFormData(prev => ({ ...prev, field1: e.target.value }))
    if (formErrors.field1) {
      setFormErrors(prev => ({ ...prev, field1: undefined }))
    }
  }}
  className={formErrors.field1 ? "border-destructive" : ""}
/>

// 4. Display error
{formErrors.field1 && (
  <p className="text-sm text-destructive">{formErrors.field1}</p>
)}
```

### قوانین Validation

1. **Real-time validation** - Clear error on change
2. **Visual feedback** - Border قرمز برای invalid fields
3. **Error messages** - زیر هر فیلد نمایش بده
4. **Required fields** - با `*` علامت بزن

---

## Accessibility Requirements

### ✅ استاندارد Accessibility

```typescript
// 1. Icon-only buttons - ALWAYS add aria-label
<Button
  variant="ghost"
  size="icon"
  aria-label="Edit item"
  title="Edit item"
>
  <Edit className="h-4 w-4" aria-hidden="true" />
</Button>

// 2. Form labels - ALWAYS use Label component
<Label htmlFor="field1">Field 1 *</Label>
<Input id="field1" />

// 3. Loading states - ALWAYS provide text alternative
{loading ? (
  <>
    <Loader2 className="h-4 w-4 animate-spin" aria-label="Loading" />
    <span className="sr-only">Loading...</span>
  </>
) : (
  "Save"
)}

// 4. Error messages - Associate with fields
<div className="space-y-2">
  <Label htmlFor="field1">Field 1</Label>
  <Input
    id="field1"
    aria-invalid={!!formErrors.field1}
    aria-describedby={formErrors.field1 ? "field1-error" : undefined}
  />
  {formErrors.field1 && (
    <p id="field1-error" className="text-sm text-destructive" role="alert">
      {formErrors.field1}
    </p>
  )}
</div>
```

### قوانین Accessibility

1. **Icon-only buttons**: `aria-label` + `title` الزامی است
2. **Form labels**: همیشه از `Label` با `htmlFor` استفاده کن
3. **Loading states**: `aria-label` یا `sr-only` text
4. **Error messages**: `role="alert"` و `aria-describedby`
5. **Keyboard navigation**: Tab order منطقی
6. **Focus indicators**: قابل مشاهده باشند

---

## Keyboard Navigation

### ✅ استاندارد Keyboard Support

```typescript
// 1. Enter key - Form submission (automatic with <form>)
<form onSubmit={handleSubmit}>
  <Input />
  <Button type="submit">Submit</Button>
</form>

// 2. Escape key - Dialog close (automatic with Radix UI Dialog)
<Dialog open={showDialog} onOpenChange={setShowDialog}>
  {/* Escape key works automatically */}
</Dialog>

// 3. Custom keyboard shortcuts
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape" && showDialog) {
      setShowDialog(false)
    }
  }
  
  window.addEventListener("keydown", handleKeyDown)
  return () => window.removeEventListener("keydown", handleKeyDown)
}, [showDialog])
```

### قوانین Keyboard Navigation

1. **Enter key**: برای submit forms (با `<form>`)
2. **Escape key**: برای بستن dialogs (Radix UI)
3. **Tab order**: منطقی و قابل پیش‌بینی
4. **Focus management**: Focus trap در dialogs

---

## Checklist برای هر Feature جدید

قبل از commit، این موارد را بررسی کن:

### Form
- [ ] از `<form>` با `onSubmit` استفاده شده
- [ ] Validation errors در state نگه داشته می‌شوند
- [ ] Field-level errors نمایش داده می‌شوند
- [ ] Invalid fields با border قرمز highlight شده‌اند
- [ ] Errors هنگام تغییر فیلد clear می‌شوند
- [ ] Enter key کار می‌کند

### Dialog
- [ ] از `ConfirmationDialog` استفاده شده (نه `confirm()`)
- [ ] State هنگام بستن reset می‌شود
- [ ] Errors هنگام بستن clear می‌شوند
- [ ] Escape key کار می‌کند

### Loading
- [ ] Page-level: از `PageLoader` استفاده شده
- [ ] Button-level: از `Loader2` با spinner استفاده شده
- [ ] Message نمایش داده می‌شود
- [ ] Buttons در حین loading disable هستند

### Error Handling
- [ ] Toast notifications برای errors
- [ ] User-friendly error messages
- [ ] Field-level errors برای validation

### Accessibility
- [ ] Icon-only buttons: `aria-label` + `title`
- [ ] Form labels: `Label` با `htmlFor`
- [ ] Loading states: `aria-label` یا text
- [ ] Error messages: `role="alert"`

### Keyboard
- [ ] Enter key برای forms
- [ ] Escape key برای dialogs
- [ ] Tab order منطقی

---

## مثال کامل

برای مثال کامل، به فایل‌های زیر مراجعه کن:
- `frontend/app/relationships/page.tsx` - Form + Dialog + Validation
- `frontend/app/data-dictionary/page.tsx` - Edit Dialog Pattern
- `frontend/app/database/page.tsx` - Delete Confirmation Pattern

---

## ⚠️ مهم

**این الگوها اجباری هستند. هر کدی که از این الگوها پیروی نکند، باید refactor شود.**

**AI Development Rule**: هنگام توسعه هر feature جدید، ابتدا این سند را بخوان و از الگوها پیروی کن.



