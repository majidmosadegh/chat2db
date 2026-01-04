# معماری ماژول Frontend Core

## نمای کلی (Overview)

ماژول **Frontend Core** رابط کاربری مدرن و responsive پلتفرم SQL PT است که با استفاده از Next.js 14، TypeScript و Tailwind CSS پیاده‌سازی شده. این ماژول یک تجربه کاربری یکپارچه برای مدیریت پایگاه داده، تولید کوئری SQL و چت تعاملی فراهم می‌کند.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                 Frontend Core                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Next.js App Router                      │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │   Pages     │   API       │   Components    │    │    │
│  │  │   (Routes)  │   Routes    │   (UI/Feature)  │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │             Design System & State                   │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │Design System│ Theme       │   API Client    │    │    │
│  │  │             │ Provider    │   & Hooks       │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   Backend API       │
           │   (FastAPI)         │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. App Router Structure (Next.js 14)

استفاده از App Router برای routing و layout management:

#### ساختار صفحات:
```
app/
├── layout.tsx              # Root layout with providers
├── page.tsx               # Dashboard/Home page
├── globals.css            # Global styles
├── chat/
│   └── page.tsx           # Chat interface
├── database/
│   └── page.tsx           # Database management
├── schema/
│   ├── page.tsx           # Schema overview
│   └── [snapshot_id]/
│       ├── page.tsx       # Schema details
│       └── relationships/
│           └── page.tsx   # Relationship visualization
├── data-dictionary/
│   └── page.tsx           # Data dictionary management
└── api/                   # API routes (server-side)
    ├── database/
    ├── schema/
    ├── chat/
    └── ...
```

#### Layout System:
```tsx
// app/layout.tsx
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        <ThemeProvider>
          <ErrorBoundary>
            <MainLayout>
              {children}
            </MainLayout>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

### 2. API Routes (Server-Side)

API routes برای ارتباط با backend:

#### ساختار API Routes:
```
api/
├── database/
│   ├── route.ts           # Database connections CRUD
│   └── test/route.ts      # Test connection
├── schema/
│   ├── route.ts           # Schema operations
│   └── snapshots/[id]/
│       ├── route.ts       # Snapshot management
│       └── activate/route.ts
├── chat/
│   └── route.ts           # Chat processing
├── data-dictionary/
│   ├── route.ts           # Dictionary operations
│   ├── column/ai-generate/route.ts
│   └── table/ai-generate/route.ts
└── models/
    ├── route.ts           # LLM models management
    └── [id]/activate/route.ts
```

#### API Route Pattern:
```typescript
// api/database/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function GET() {
  try {
    const connections = await fetchFromBackend('/api/database')
    return NextResponse.json(connections)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch connections' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const result = await postToBackend('/api/database', body)
    return NextResponse.json(result)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to create connection' },
      { status: 500 }
    )
  }
}
```

### 3. Component Architecture

سیستم کامپوننت‌ها با separation of concerns:

#### UI Components (`components/ui/`):
```tsx
// Button component with variants
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    )
  }
)
```

#### Feature Components:
```tsx
// Chat components
components/
├── chat/
│   ├── chat-header.tsx
│   ├── chat-input.tsx
│   ├── chat-message.tsx
│   ├── chat-messages.tsx
│   ├── chat-mode-selector.tsx
│   ├── chat-settings.tsx
│   ├── index.ts
│   ├── snapshot-selector.tsx
│   └── typing-indicator.tsx
```

#### Layout Components:
```tsx
// Main layout with sidebar
components/layout/
├── main-layout.tsx        # Main app layout
├── sidebar.tsx           # Navigation sidebar
└── active-snapshot-indicator.tsx
```

### 4. State Management & Hooks

مدیریت وضعیت با React Context و custom hooks:

#### API Client Hook:
```typescript
// lib/use-api-error.ts
export function useApiError() {
  const { toast } = useToast()

  const handleError = useCallback((error: ApiError) => {
    const message = getErrorMessage(error)
    toast({
      title: "Error",
      description: message,
      variant: "destructive",
    })
  }, [toast])

  return { handleError }
}
```

#### Toast Notification System:
```typescript
// lib/use-toast.ts
export const useToast = () => {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback(({ title, description, variant }: ToastProps) => {
    const id = Math.random().toString(36)
    setToasts(prev => [...prev, { id, title, description, variant }])
  }, [])

  return { toast, toasts, dismiss: (id: string) => setToasts(prev => prev.filter(t => t.id !== id)) }
}
```

### 5. Design System

سیستم طراحی یکپارچه با Tailwind CSS:

#### Theme Provider:
```tsx
// lib/theme-provider.tsx
export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider {...props}>
      <Toaster />
      {children}
    </NextThemesProvider>
  )
}
```

#### Design Tokens:
```typescript
// lib/design-system.ts
export const designSystem = {
  colors: {
    primary: {
      50: '#eff6ff',
      500: '#3b82f6',
      900: '#1e3a8a',
    },
    // ... more colors
  },
  spacing: {
    1: '0.25rem',
    2: '0.5rem',
    4: '1rem',
    // ... more spacing
  },
  typography: {
    fontSize: {
      xs: '0.75rem',
      sm: '0.875rem',
      base: '1rem',
      // ... more sizes
    },
  },
}
```

## قابلیت‌های کلیدی (Key Features)

### 1. **Responsive Design**
- Mobile-first approach
- Adaptive layouts
- Touch-friendly interactions

### 2. **Accessibility**
- Semantic HTML
- Keyboard navigation
- Screen reader support
- Focus management

### 3. **Performance Optimization**
- Code splitting
- Image optimization
- Lazy loading
- Bundle analysis

### 4. **Error Handling**
```tsx
// components/error-boundary.tsx
class ErrorBoundary extends React.Component {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to monitoring service
    console.error('Error caught by boundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />
    }

    return this.props.children
  }
}
```

### 5. **Loading States**
```tsx
// Loading components
const PageLoader = ({ message = "Loading..." }) => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="text-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
      <p className="mt-4 text-muted-foreground">{message}</p>
    </div>
  </div>
)

const SkeletonLoader = () => (
  <div className="animate-pulse">
    <div className="h-4 bg-muted rounded w-3/4 mb-2"></div>
    <div className="h-4 bg-muted rounded w-1/2"></div>
  </div>
)
```

## معماری داده (Data Flow)

### 1. **Server-Side Data Fetching**
```typescript
// API route with data fetching
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const page = searchParams.get('page') || '1'

  try {
    // Fetch from backend
    const data = await fetchBackendData('/api/schema', { page })

    // Transform data for frontend
    const transformedData = transformSchemaData(data)

    return NextResponse.json(transformedData)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch schema' },
      { status: 500 }
    )
  }
}
```

### 2. **Client-Side State Management**
```typescript
// Custom hook for data management
function useSchemaData(snapshotId: string) {
  const [data, setData] = useState<SchemaData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSchemaData(snapshotId)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [snapshotId])

  return { data, loading, error, refetch: () => fetchSchemaData(snapshotId) }
}
```

### 3. **Real-time Updates**
```typescript
// WebSocket or Server-Sent Events for real-time features
function useChatMessages(conversationId: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/chat/${conversationId}`)

    ws.onopen = () => setIsConnected(true)
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      setMessages(prev => [...prev, message])
    }
    ws.onclose = () => setIsConnected(false)

    return () => ws.close()
  }, [conversationId])

  return { messages, isConnected }
}
```

## امنیت (Security)

### 1. **Input Validation**
- Client-side validation with Zod
- Server-side validation in API routes
- Sanitization of user inputs

### 2. **Authentication & Authorization**
```typescript
// API route protection
export async function POST(request: NextRequest) {
  // Validate authentication
  const authHeader = request.headers.get('authorization')
  if (!authHeader || !isValidToken(authHeader)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // Validate permissions
  const user = getUserFromToken(authHeader)
  if (!user.canManageDatabases) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  // Proceed with operation
  // ...
}
```

### 3. **CSRF Protection**
- SameSite cookies
- CSRF tokens for forms
- Origin validation

## بهینه‌سازی عملکرد (Performance Optimization)

### 1. **Code Splitting**
```typescript
// Dynamic imports for route-based splitting
const ChatPage = dynamic(() => import('@/app/chat/page'), {
  loading: () => <PageLoader />
})

const DatabasePage = dynamic(() => import('@/app/database/page'), {
  loading: () => <PageLoader />
})
```

### 2. **Image Optimization**
```tsx
import Image from 'next/image'

<Image
  src="/database-icon.png"
  alt="Database"
  width={24}
  height={24}
  priority // For above-the-fold images
/>
```

### 3. **Caching Strategies**
```typescript
// SWR for data fetching with caching
import useSWR from 'swr'

function useDatabaseConnections() {
  const { data, error, mutate } = useSWR('/api/database', fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 5000, // 5 seconds
  })

  return {
    connections: data,
    isLoading: !error && !data,
    isError: error,
    refetch: mutate
  }
}
```

## قابلیت توسعه (Extensibility)

### افزودن صفحه جدید:
```typescript
// 1. Create page component
// app/new-feature/page.tsx
export default function NewFeaturePage() {
  return (
    <div>
      <h1>New Feature</h1>
      {/* Page content */}
    </div>
  )
}

// 2. Add API routes if needed
// app/api/new-feature/route.ts
export async function GET() {
  // API logic
}

// 3. Create feature components
// components/new-feature/index.tsx
export function NewFeatureComponent() {
  // Component logic
}
```

### افزودن کامپوننت UI جدید:
```tsx
// components/ui/new-component.tsx
interface NewComponentProps {
  variant?: 'primary' | 'secondary'
  children: React.ReactNode
}

export const NewComponent = React.forwardRef<HTMLDivElement, NewComponentProps>(
  ({ className, variant = 'primary', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(newComponentVariants({ variant }), className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
```

## تنظیمات و Configuration

### Environment Variables:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_ENVIRONMENT=development
```

### Build Configuration:
```javascript
// next.config.js
module.exports = {
  experimental: {
    appDir: true,
  },
  images: {
    domains: ['localhost'],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },
}
```

## مزایای معماری (Architecture Benefits)

### 1. **Developer Experience**
- TypeScript for type safety
- Hot reload for development
- Comprehensive tooling

### 2. **Performance**
- Server-side rendering
- Static generation where possible
- Optimized bundle splitting

### 3. **Maintainability**
- Component-based architecture
- Clear separation of concerns
- Consistent design system

### 4. **Scalability**
- Modular component structure
- Lazy loading
- Efficient state management

## چالش‌ها و محدودیت‌ها (Challenges & Limitations)

### 1. **Hydration Issues**
- Server/client rendering mismatches
- Complex state synchronization

### 2. **Bundle Size**
- Large JavaScript bundles
- Third-party library management

### 3. **SEO Considerations**
- Dynamic content optimization
- Meta tag management

## بهبودهای آینده (Future Enhancements)

### 1. **Advanced State Management**
- Zustand or Redux Toolkit integration
- Server state management
- Real-time synchronization

### 2. **Progressive Web App (PWA)**
- Offline functionality
- Service workers
- Push notifications

### 3. **Internationalization**
- Multi-language support
- RTL language handling
- Date/number formatting

### 4. **Component Library**
- Storybook integration
- Automated testing
- Design system documentation

---

**معماری Frontend Core یک foundation قوی برای توسعه رابط کاربری مدرن و مقیاس‌پذیر فراهم می‌کند که تجربه کاربری عالی را تضمین می‌کند.**









