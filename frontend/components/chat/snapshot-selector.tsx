"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Database, CheckCircle, AlertCircle } from "lucide-react"

interface Snapshot {
  id: number
  name: string
  description?: string
  connection_id: number
  created_at: string
  table_count: number
}

interface SnapshotSelectorProps {
  onSnapshotSelect: (snapshotId: number) => void
  selectedSnapshotId?: number | null
}

export function SnapshotSelector({ onSnapshotSelect, selectedSnapshotId }: SnapshotSelectorProps) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSnapshots()
  }, [])

  const loadSnapshots = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/schema/snapshots')
      if (!response.ok) throw new Error('Failed to load snapshots')

      const data = await response.json()
      setSnapshots(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load snapshots')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <Card className="mb-4">
        <CardContent className="p-4">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span>Loading database snapshots...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="mb-4 border-red-200">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-red-600">
            <AlertCircle className="h-4 w-4" />
            <span>Failed to load snapshots: {error}</span>
          </div>
          <Button
            onClick={loadSnapshots}
            variant="outline"
            size="sm"
            className="mt-2"
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (snapshots.length === 0) {
    return (
      <Card className="mb-4 border-yellow-200">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-yellow-600">
            <AlertCircle className="h-4 w-4" />
            <span>No database snapshots found. Please create a database connection first.</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="mb-4">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Database className="h-4 w-4" />
          Select Database Snapshot
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <Select
            value={selectedSnapshotId?.toString() || ""}
            onValueChange={(value) => onSnapshotSelect(parseInt(value))}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose a database snapshot..." />
            </SelectTrigger>
            <SelectContent>
              {snapshots.map((snapshot) => (
                <SelectItem key={snapshot.id} value={snapshot.id.toString()}>
                  <div className="flex items-center gap-2">
                    <Database className="h-3 w-3" />
                    <span>{snapshot.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {snapshot.table_count} tables
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {selectedSnapshotId && (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" />
              <span>Snapshot selected. You can now start chatting!</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}