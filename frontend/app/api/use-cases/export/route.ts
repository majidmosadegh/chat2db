import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const snapshotId = searchParams.get('snapshot_id')

    let url = `${BACKEND_URL}/api/use-cases/export/csv`
    if (snapshotId) {
      url += `?snapshot_id=${snapshotId}`
    }

    console.log('Fetching CSV from backend:', url)

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'text/csv',
      },
    })

    console.log('Backend response status:', response.status, response.statusText)
    console.log('Backend response headers:', Object.fromEntries(response.headers.entries()))

    if (!response.ok) {
      let errorText = ''
      try {
        errorText = await response.text()
        console.error('Backend export error:', errorText)
      } catch (e) {
        errorText = `HTTP ${response.status}: ${response.statusText}`
        console.error('Failed to read error response:', e)
      }
      return NextResponse.json(
        { error: `Failed to export use cases: ${errorText}` },
        { status: response.status }
      )
    }

    // Get the CSV content as array buffer to preserve encoding
    const csvBuffer = await response.arrayBuffer()
    
    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get("Content-Disposition")
    let filename = `use_cases_${new Date().toISOString().split('T')[0]}.csv`
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/i)
      if (filenameMatch) {
        filename = filenameMatch[1].replace(/['"]/g, '').trim()
        // Remove trailing underscores
        filename = filename.replace(/_+$/, '')
        // Ensure it ends with .csv
        if (!filename.endsWith('.csv')) {
          filename = filename.replace(/\.csv_*$/, '.csv')
        }
      }
    }

    // Return CSV file with proper headers
    return new NextResponse(csvBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8-sig',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    })
  } catch (error) {
    console.error('Failed to export use cases:', error)
    return NextResponse.json(
      { error: 'Failed to export use cases' },
      { status: 500 }
    )
  }
}

