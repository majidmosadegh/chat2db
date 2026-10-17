export enum ErrorType {
  CLIENT = "CLIENT",
  NETWORK = "NETWORK",
  SERVER = "SERVER",
  VALIDATION = "VALIDATION",
  UNKNOWN = "UNKNOWN",
}

export interface AppError {
  type: ErrorType
  message: string
  userMessage: string
  timestamp: Date
  cause?: unknown
  context?: Record<string, unknown>
}

export function createAppError(
  cause: unknown,
  context: Record<string, unknown> = {},
  options: Partial<Pick<AppError, "type" | "message" | "userMessage">> = {}
): AppError {
  const fallbackMessage =
    cause instanceof Error ? cause.message : "Unexpected application error"

  return {
    type: options.type ?? ErrorType.UNKNOWN,
    message: options.message ?? fallbackMessage,
    userMessage:
      options.userMessage ??
      "Something went wrong. Please try again or refresh the page.",
    timestamp: new Date(),
    cause,
    context,
  }
}

export function logError(error: AppError): void {
  if (typeof console !== "undefined") {
    console.error("[chat2db]", error.message, {
      type: error.type,
      userMessage: error.userMessage,
      context: error.context,
      cause: error.cause,
    })
  }
}

export function showErrorToast(error: AppError): void {
  // Lazy import avoids circular dependency with toast state during SSR.
  void import("@/lib/use-toast").then(({ toast }) => {
    toast({
      variant: "destructive",
      title: error.message,
      description: error.userMessage,
    })
  })
}
