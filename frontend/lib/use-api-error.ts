"use client"

import { useCallback, useState } from "react"

import {
  AppError,
  createAppError,
  ErrorType,
  logError,
  showErrorToast,
} from "@/lib/error-handler"

export function useApiError() {
  const [error, setError] = useState<AppError | null>(null)

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const handleError = useCallback((err: unknown, userMessage?: string) => {
    const appError = createAppError(
      err,
      {},
      {
        type: ErrorType.NETWORK,
        message: "API request failed",
        userMessage:
          userMessage ??
          "The request failed. Check the backend connection and try again.",
      }
    )
    setError(appError)
    logError(appError)
    showErrorToast(appError)
    return appError
  }, [])

  const withErrorHandling = useCallback(
    async <T,>(fn: () => Promise<T>, userMessage?: string): Promise<T | null> => {
      try {
        clearError()
        return await fn()
      } catch (err) {
        handleError(err, userMessage)
        return null
      }
    },
    [clearError, handleError]
  )

  return {
    error,
    isError: error !== null,
    clearError,
    handleError,
    withErrorHandling,
  }
}
