"use client"

import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { BookOpen, AlertCircle } from "lucide-react"

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  connection_id: number
  is_active: boolean
  created_at: string
  table_count: number
}

export function ActiveSnapshotIndicator() {
  const [activeSnapshot, setActiveSnapshot] = useState<SchemaSnapshot | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchActiveSnapshot()
  }, [])

  const fetchActiveSnapshot = async () => {
    try {
      const response = await fetch("/api/schema/snapshots")
      if (response.ok) {
        const snapshots = await response.json()
        const active = snapshots.find((s: SchemaSnapshot) => s.is_active) || null
        setActiveSnapshot(active)
      }
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <BookOpen className="h-4 w-4" />
        <span>Loading snapshot status...</span>
      </div>
    )
  }

  if (!activeSnapshot) {
    return (
      <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
        <AlertCircle className="h-4 w-4" />
        <span>No active schema snapshot</span>
        <Badge variant="outline" className="text-xs">
          Data Dictionary disabled
        </Badge>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <BookOpen className="h-4 w-4 text-green-600" />
      <span className="font-medium">Active Snapshot:</span>
      <Badge variant="default" className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
        {activeSnapshot.name}
      </Badge>
      <span className="text-muted-foreground">
        ({activeSnapshot.table_count} tables)
      </span>
      {activeSnapshot.description && (
        <span className="text-muted-foreground text-xs max-w-md truncate">
          {activeSnapshot.description}
        </span>
      )}
    </div>
  )
}