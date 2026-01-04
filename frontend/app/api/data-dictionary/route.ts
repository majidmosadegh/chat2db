import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const snapshotId = searchParams.get('snapshot_id')

    const backendUrl = snapshotId
      ? `http://localhost:8000/api/data-dictionary?snapshot_id=${snapshotId}`
      : 'http://localhost:8000/api/data-dictionary'

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

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const url = new URL(request.url)
    const entryId = url.pathname.split('/').pop()

    const response = await fetch(`http://localhost:8000/api/data-dictionary/${entryId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const responseText = await response.text()

    if (!response.ok) {
      try {
        const error = JSON.parse(responseText)
        return NextResponse.json(error, { status: response.status })
      } catch (jsonError) {
        return NextResponse.json({ detail: responseText }, { status: response.status })
      }
    }

    try {
      const data = JSON.parse(responseText)
      return NextResponse.json(data)
    } catch (jsonError) {
      return NextResponse.json({ detail: "Invalid JSON response from backend" }, { status: 500 })
    }
  } catch (error: any) {
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const pathParts = url.pathname.split('/')
    const action = pathParts[pathParts.length - 1]

    if (action === 'ai-generate') {
      // Start async AI generation job
      const response = await fetch(`${BACKEND_URL}/api/data-dictionary/ai-generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(await request.json())
      })

      const responseText = await response.text()

      if (!response.ok) {
        try {
          const error = JSON.parse(responseText)
          return NextResponse.json(error, { status: response.status })
        } catch (jsonError) {
          return NextResponse.json({ detail: responseText }, { status: response.status })
        }
      }

      try {
        const data = JSON.parse(responseText)
        return NextResponse.json(data)
      } catch (jsonError) {
        return NextResponse.json({ detail: "Invalid JSON response from backend" }, { status: 500 })
      }
    }

    // Handle regular POST for creating entries
    const body = await request.json()

    const response = await fetch(`http://localhost:8000/api/data-dictionary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const responseText = await response.text()

    if (!response.ok) {
      try {
        const error = JSON.parse(responseText)
        return NextResponse.json(error, { status: response.status })
      } catch (jsonError) {
        return NextResponse.json({ detail: responseText }, { status: response.status })
      }
    }

    try {
      const data = JSON.parse(responseText)
      return NextResponse.json(data)
    } catch (jsonError) {
      return NextResponse.json({ detail: "Invalid JSON response from backend" }, { status: 500 })
    }
  } catch (error: any) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}