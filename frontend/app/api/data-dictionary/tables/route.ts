import { NextRequest, NextResponse } from 'next/server'
import { createAppError, showErrorToast, logError, ErrorType } from '@/lib/error-handler'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const snapshotId = searchParams.get('snapshot_id')

    // Validate required parameters
    if (!snapshotId) {
      const appError = createAppError(
        new Error('Snapshot ID is required'),
        { endpoint: '/api/data-dictionary/tables', method: 'GET' },
        {
          type: ErrorType.VALIDATION,
          message: 'Missing required parameter',
          userMessage: 'Please provide a valid snapshot ID'
        }
      )
      logError(appError)

      return NextResponse.json(
        {
          error: appError.message,
          message: appError.userMessage,
          code: 'VALIDATION_ERROR'
        },
        { status: 400 }
      )
    }

    const backendUrl = new URL('/api/data-dictionary/tables', BACKEND_URL)
    backendUrl.searchParams.set('snapshot_id', snapshotId)

    const response = await fetch(backendUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      let errorMessage = 'Failed to fetch data dictionary tables'
      let statusCode = response.status

      try {
        const errorData = await response.json()
        errorMessage = errorData.message || errorData.error || errorMessage
      } catch {
        // If we can't parse the error response, use a generic message
      }

      const appError = createAppError(
        new Error(errorMessage),
        {
          endpoint: '/api/data-dictionary/tables',
          method: 'GET',
          snapshotId,
          backendUrl: backendUrl.toString(),
          backendStatus: response.status
        }
      )
      logError(appError)

      return NextResponse.json(
        {
          error: appError.message,
          message: appError.userMessage,
          code: getErrorCodeFromStatus(response.status),
          details: {
            snapshot_id: snapshotId
          }
        },
        { status: statusCode }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    const appError = createAppError(
      error,
      {
        endpoint: '/api/data-dictionary/tables',
        method: 'GET',
        snapshotId: new URL(request.url).searchParams.get('snapshot_id')
      }
    )
    logError(appError)

    return NextResponse.json(
      {
        error: appError.message,
        message: appError.userMessage,
        code: 'INTERNAL_ERROR',
        details: {
          timestamp: appError.timestamp.toISOString()
        }
      },
      { status: 500 }
    )
  }
}

// Helper function to map HTTP status codes to error codes
function getErrorCodeFromStatus(status: number): string {
  const statusMap: Record<number, string> = {
    400: 'VALIDATION_ERROR',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    429: 'RATE_LIMIT_EXCEEDED',
    500: 'INTERNAL_ERROR',
    502: 'EXTERNAL_API_ERROR',
    503: 'SERVICE_UNAVAILABLE',
    504: 'TIMEOUT_ERROR'
  }

  return statusMap[status] || 'UNKNOWN_ERROR'
}
