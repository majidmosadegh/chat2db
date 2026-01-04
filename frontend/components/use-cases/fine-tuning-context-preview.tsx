"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Database, FileText, Link, CheckCircle } from "lucide-react"
import axios from "axios"

interface ContextPreviewData {
  tables: Array<{
    name: string
    columns: Array<{
      name: string
      type: string
      is_primary_key: boolean
      is_foreign_key: boolean
    }>
    row_count: number
  }>
  relationships: Array<{
    source_table: string
    source_column: string
    target_table: string
    target_column: string
    relationship_type: string
    join_type: string
    description: string
  }>
  data_dictionary_coverage: {
    total_tables: number
    tables_with_descriptions: number
    total_columns: number
    columns_with_descriptions: number
    coverage_percentage: number
  }
  use_case_text: string
}

interface FineTuningContextPreviewProps {
  sessionId: number
  onNext: () => void
}

export function FineTuningContextPreview({ sessionId, onNext }: FineTuningContextPreviewProps) {
  const [data, setData] = useState<ContextPreviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [includeDictionary, setIncludeDictionary] = useState<boolean>(false)

  useEffect(() => {
    fetchContextData()
  }, [sessionId])

  const fetchContextData = async () => {
    try {
      const response = await axios.get(`/api/fine-tuning/sessions/${sessionId}/context`)
      setData(response.data)
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p>Loading context data...</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500">Failed to load context data</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">Context Preview</h2>
        <p className="text-muted-foreground">
          Review the database schema, relationships, and data dictionary before fine-tuning
        </p>
      </div>

      {/* Current Use Case */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Current Use Case
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{data.use_case_text}</p>
        </CardContent>
      </Card>

      {/* Data Dictionary Coverage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Data Dictionary Coverage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {data.data_dictionary_coverage.tables_with_descriptions}
              </div>
              <div className="text-sm text-muted-foreground">
                of {data.data_dictionary_coverage.total_tables} tables
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {data.data_dictionary_coverage.columns_with_descriptions}
              </div>
              <div className="text-sm text-muted-foreground">
                of {data.data_dictionary_coverage.total_columns} columns
              </div>
            </div>
            <div className="text-center col-span-2">
              <div className="text-2xl font-bold text-purple-600">
                {Math.round(data.data_dictionary_coverage.coverage_percentage)}%
              </div>
              <div className="text-sm text-muted-foreground">Overall coverage</div>
            </div>
          </div>

          {/* تنظیمات include dictionary در مرحله اولیه انجام شده */}
        </CardContent>
      </Card>

      {/* Tables Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Tables Involved ({data.tables.length})
          </CardTitle>
          <CardDescription>
            Database tables that will be available during fine-tuning
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            {data.tables.map((table) => (
              <Card key={table.name} className="border-l-4 border-l-blue-500">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex items-center justify-between">
                    {table.name}
                    <Badge variant="outline">{table.row_count} rows</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {table.columns.slice(0, 5).map((column) => (
                      <div key={column.name} className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-xs bg-gray-100 px-1 py-0.5 rounded">
                          {column.type}
                        </span>
                        <span>{column.name}</span>
                        {column.is_primary_key && (
                          <Badge variant="default" className="text-xs">PK</Badge>
                        )}
                        {column.is_foreign_key && (
                          <Badge variant="secondary" className="text-xs">FK</Badge>
                        )}
                      </div>
                    ))}
                    {table.columns.length > 5 && (
                      <p className="text-xs text-muted-foreground">
                        +{table.columns.length - 5} more columns
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Relationships */}
      {data.relationships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link className="h-5 w-5" />
              Table Relationships ({data.relationships.length})
            </CardTitle>
            <CardDescription>
              Defined relationships between tables
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.relationships.map((rel, index) => (
                  <TableRow key={index}>
                    <TableCell className="font-mono text-sm">
                      {rel.source_table}.{rel.source_column}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {rel.target_table}.{rel.target_column}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{rel.join_type}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{rel.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button variant="outline">
          Cancel
        </Button>
        <Button onClick={onNext} className="gap-2">
          <CheckCircle className="h-4 w-4" />
          Continue to Question Generation
        </Button>
      </div>
    </div>
  )
}
