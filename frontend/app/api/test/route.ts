import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    // Test the data dictionary endpoints
    const [schemaResponse, dictResponse] = await Promise.all([
      fetch('http://localhost:8000/api/schema/tables?snapshot_id=11'),
      fetch('http://localhost:8000/api/data-dictionary?snapshot_id=11')
    ])

    const schemaData = schemaResponse.ok ? await schemaResponse.json() : []
    const dictData = dictResponse.ok ? await dictResponse.json() : []

    return NextResponse.json({
      message: 'Data dictionary test',
      timestamp: new Date().toISOString(),
      schemaTables: schemaData.length,
      dictEntries: dictData.length,
      sampleSchema: schemaData[0] ? {
        name: schemaData[0].table_name,
        columns: schemaData[0].columns?.length || 0
      } : null
    })
  } catch (error: any) {
    return NextResponse.json({
      error: error.message,
      timestamp: new Date().toISOString()
    })
  }
}
