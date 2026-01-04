import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_URL}/api/data-dictionary/table/ai-generate`, {
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
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

