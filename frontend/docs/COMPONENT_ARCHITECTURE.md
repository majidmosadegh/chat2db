# Component Architecture & File Structure

این سند ساختار و معماری کامپوننت‌ها را تعریف می‌کند.

## 📁 ساختار فایل‌ها

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── [route]/page.tsx   # Page components
│   └── api/               # API routes
├── components/            # React components
│   ├── ui/               # Base UI components (shadcn/ui)
│   ├── [feature]/        # Feature-specific components
│   └── layout/           # Layout components
├── lib/                  # Utilities & hooks
│   ├── utils.ts         # General utilities
│   ├── use-toast.ts     # Toast hook
│   └── design-system.ts # Design system constants
└── docs/                 # Documentation
    ├── UI_UX_PATTERNS.md
    └── COMPONENT_ARCHITECTURE.md
```

## 🧩 Component Categories

### 1. Base UI Components (`components/ui/`)

کامپوننت‌های پایه از shadcn/ui. **نباید مستقیماً تغییر داده شوند.**

- `button.tsx` - Button component
- `dialog.tsx` - Dialog/Modal component
- `input.tsx` - Input field
- `textarea.tsx` - Textarea field
- `select.tsx` - Select dropdown
- `card.tsx` - Card container
- `badge.tsx` - Badge component
- `loading.tsx` - Loading states (PageLoader, ButtonLoader, etc.)
- `confirmation-dialog.tsx` - Delete confirmation dialog
- `enhanced-empty-state.tsx` - Empty state component

### 2. Feature Components (`components/[feature]/`)

کامپوننت‌های مربوط به feature خاص.

```
components/
├── chat/              # Chat feature components
├── relationships/     # Relationships feature
├── use-cases/        # Use cases feature
└── layout/           # Layout components
```

### 3. Page Components (`app/[route]/page.tsx`)

صفحات اصلی application. باید از الگوهای `UI_UX_PATTERNS.md` پیروی کنند.

## 📝 Naming Conventions

### Files
- **Components**: `kebab-case.tsx` - `user-profile.tsx`
- **Pages**: `page.tsx` - Next.js convention
- **Utilities**: `kebab-case.ts` - `format-date.ts`
- **Hooks**: `use-kebab-case.ts` - `use-api-error.ts`

### Components
- **Function components**: `PascalCase` - `UserProfile`
- **Props interfaces**: `ComponentNameProps` - `UserProfileProps`
- **State interfaces**: `ComponentNameState` - `UserProfileState`

### Variables
- **State**: `camelCase` - `userData`, `isLoading`
- **Constants**: `UPPER_SNAKE_CASE` - `MAX_RETRIES`, `API_BASE_URL`
- **Functions**: `camelCase` - `handleSubmit`, `validateForm`

## 🏗️ Component Structure Template

```typescript
"use client"

// 1. Imports - Grouped by type
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { useToast } from "@/lib/use-toast"

// 2. Type Definitions
interface ComponentProps {
  // Props
}

interface ComponentState {
  // State structure
}

// 3. Constants (if any)
const CONSTANT_VALUE = "value"

// 4. Main Component
export default function ComponentName(props: ComponentProps) {
  // Implementation
}

// 5. Helper Functions (if any)
function helperFunction() {
  // Helper logic
}
```

## 🔄 State Management Pattern

### Local State (useState)
برای state محلی کامپوننت استفاده می‌شود.

```typescript
const [loading, setLoading] = useState(false)
const [data, setData] = useState<DataType | null>(null)
const [errors, setErrors] = useState<ErrorsType>({})
```

### Server State (useEffect + fetch)
برای fetch کردن data از API.

```typescript
useEffect(() => {
  const fetchData = async () => {
    try {
      setLoading(true)
      const response = await fetch("/api/endpoint")
      const data = await response.json()
      setData(data)
    } catch (error) {
      // Error handling
    } finally {
      setLoading(false)
    }
  }
  
  fetchData()
}, [])
```

## 🎨 Styling Guidelines

### Tailwind CSS Classes
- از utility classes استفاده کن
- از design system constants استفاده کن (`@/lib/design-system`)
- Responsive: `sm:`, `md:`, `lg:` prefixes

### Class Organization
```typescript
className={cn(
  "base-classes",
  condition && "conditional-classes",
  className // Allow override
)}
```

## 📦 Component Composition

### Compound Components
برای components پیچیده، از composition استفاده کن:

```typescript
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>
    Content
  </CardContent>
</Card>
```

### Component Props
```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline"
  size?: "sm" | "md" | "lg"
  loading?: boolean
  children: React.ReactNode
}
```

## 🧪 Testing Considerations

### Component Structure
- Components باید testable باشند
- Logic را از UI جدا کن
- Custom hooks برای complex logic

## 📚 Best Practices

1. **Single Responsibility**: هر component یک کار انجام دهد
2. **Composition over Inheritance**: از composition استفاده کن
3. **Props Interface**: همیشه interface برای props تعریف کن
4. **Type Safety**: از TypeScript استفاده کن
5. **Reusability**: Components قابل استفاده مجدد بساز
6. **Documentation**: Complex logic را document کن

## 🔗 Related Documentation

- [UI/UX Patterns](./UI_UX_PATTERNS.md) - Development patterns
- [Design System](../lib/design-system.ts) - Design constants



