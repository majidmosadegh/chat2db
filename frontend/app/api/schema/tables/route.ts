import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    // Get snapshot_id from query parameters
    const { searchParams } = new URL(request.url)
    const snapshotId = searchParams.get('snapshot_id')

    if (!snapshotId) {
      return NextResponse.json(
        { error: 'snapshot_id query parameter is required' },
        { status: 400 }
      )
    }

    const backendUrl = `http://localhost:8000/api/schema/tables?snapshot_id=${snapshotId}`

    const response = await fetch(backendUrl)

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend returned ${response.status}` },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    )
  }
}
