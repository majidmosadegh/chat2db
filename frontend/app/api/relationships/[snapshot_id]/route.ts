import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ snapshot_id: string }> }
) {
  try {
    const { snapshot_id: snapshotId } = await params
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()
    const backendUrl = queryString
      ? `${BACKEND_URL}/api/relationships/${snapshotId}?${queryString}`
      : `${BACKEND_URL}/api/relationships/${snapshotId}`

    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch relationships' },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

