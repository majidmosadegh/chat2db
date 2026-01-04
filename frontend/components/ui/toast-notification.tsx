"use client"

import { useEffect, useState } from "react"
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

export type ToastType = "success" | "error" | "warning" | "info"

interface ToastProps {
  id: string
  type: ToastType
  title: string
  description?: string
  duration?: number
  onClose: (id: string) => void
}

const toastIcons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const toastStyles = {
  success: "bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-300",
  error: "bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-300",
  warning: "bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-950 dark:border-yellow-800 dark:text-yellow-300",
  info: "bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-300",
}

function Toast({ id, type, title, description, duration = 5000, onClose }: ToastProps) {
  const [isVisible, setIsVisible] = useState(true)
  const Icon = toastIcons[type]

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        handleClose()
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [duration])

  const handleClose = () => {
    setIsVisible(false)
    setTimeout(() => onClose(id), 300) // Wait for animation to complete
  }

  return (
    <div
      className={cn(
        "relative flex items-start gap-3 rounded-lg border p-4 shadow-lg transition-all duration-300 ease-in-out",
        toastStyles[type],
        isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-full"
      )}
    >
      <Icon className="mt-0.5 h-5 w-5 flex-shrink-0" />
      <div className="flex-1 space-y-1">
        <h4 className="text-sm font-semibold">{title}</h4>
        {description && (
          <p className="text-sm opacity-90">{description}</p>
        )}
      </div>
      <button
        onClick={handleClose}
        className="flex-shrink-0 rounded-md p-1 opacity-70 transition-opacity hover:opacity-100"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Progress bar for auto-dismiss */}
      {duration > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-current opacity-20">
          <div
            className="h-full bg-current opacity-60 animate-progress-bar"
            style={{
              animationDuration: `${duration}ms`,
              animationTimingFunction: "linear",
            }}
          />
        </div>
      )}
    </div>
  )
}

interface ToastContainerProps {
  toasts: Array<Omit<ToastProps, "onClose">>
  onRemove: (id: string) => void
  position?: "top-right" | "top-left" | "bottom-right" | "bottom-left" | "top-center" | "bottom-center"
}

export function ToastContainer({
  toasts,
  onRemove,
  position = "top-right"
}: ToastContainerProps) {
  const positionClasses = {
    "top-right": "top-4 right-4",
    "top-left": "top-4 left-4",
    "bottom-right": "bottom-4 right-4",
    "bottom-left": "bottom-4 left-4",
    "top-center": "top-4 left-1/2 transform -translate-x-1/2",
    "bottom-center": "bottom-4 left-1/2 transform -translate-x-1/2",
  }

  return (
    <div
      className={cn(
        "fixed z-50 flex flex-col gap-2",
        positionClasses[position]
      )}
    >
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          {...toast}
          onClose={onRemove}
        />
      ))}
    </div>
  )
}

// Toast hook for managing toast state
export function useToast() {
  const [toasts, setToasts] = useState<Array<ToastProps & { id: string }>>([])

  const addToast = (toast: Omit<ToastProps, "id" | "onClose">) => {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast: ToastProps & { id: string } = {
      ...toast,
      id,
      onClose: () => {} // This will be overridden when rendering
    }

    setToasts((prev) => [...prev, newToast])

    // Auto remove after duration + animation time
    setTimeout(() => {
      removeToast(id)
    }, (toast.duration || 5000) + 300)
  }

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }

  const success = (title: string, description?: string, duration?: number) => {
    addToast({ type: "success", title, description, duration })
  }

  const error = (title: string, description?: string, duration?: number) => {
    addToast({ type: "error", title, description, duration })
  }

  const warning = (title: string, description?: string, duration?: number) => {
    addToast({ type: "warning", title, description, duration })
  }

  const info = (title: string, description?: string, duration?: number) => {
    addToast({ type: "info", title, description, duration })
  }

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info,
  }
}

// Add progress bar animation to CSS
const progressBarStyles = `
@keyframes progress-bar {
  from {
    width: 100%;
  }
  to {
    width: 0%;
  }
}

.animate-progress-bar {
  animation: progress-bar linear;
}
`

// Inject styles (only run once)
if (typeof document !== "undefined") {
  const style = document.createElement("style")
  style.textContent = progressBarStyles
  document.head.appendChild(style)
}














