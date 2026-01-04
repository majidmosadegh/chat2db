"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Database,
  Edit,
  Save,
  Loader2,
  ChevronRight,
  ChevronDown,
  BookOpen,
  Sparkles,
  CheckCircle,
  AlertCircle,
  Play,
  Pause,
  Square,
  BarChart3,
  Clock,
  Download
} from "lucide-react"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { EnhancedEmptyState } from "@/components/ui/enhanced-empty-state"
import { PageLoader } from "@/components/ui/loading"

// Types
interface TableDictionary {
  schema_name: string
  table_name: string
  row_count?: number
  description?: string
  example_values?: string[]
  is_sensitive?: boolean
  is_ai_generated?: boolean
  columns: Array<{
    name: string
    type: string
    is_primary_key?: boolean
    is_foreign_key?: boolean
    description?: string
    example_values?: string[]
    synonyms?: string
    is_sensitive?: boolean
    is_ai_generated?: boolean
  }>
}

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  table_count: number
}

interface EditingEntry {
  schema_name: string
  table_name: string
  column_name?: string
  description: string
  example_values: string
  synonyms: string
  is_sensitive: boolean
}

interface AIJob {
  job_id: string
  snapshot_id: number
  status: 'waiting' | 'processing' | 'completed' | 'failed' | 'paused' | 'canceled'
  total_tables: number
  completed_tables: number
  current_table?: string
  created_at: string
  updated_at: string
  business_domain?: string
  database_description?: string
  target_user?: string
  language?: string
  progress?: any
}

export default function DataDictionaryPage() {
  const { toast } = useToast()
  const router = useRouter()

  // State
  const [selectedSnapshot, setSelectedSnapshot] = useState<SchemaSnapshot | null>(null)
  const [schemaSnapshots, setSchemaSnapshots] = useState<SchemaSnapshot[]>([])
  const [tableData, setTableData] = useState<TableDictionary[]>([])
  const [loading, setLoading] = useState(false)

  // Edit dialog state
  const [editingEntry, setEditingEntry] = useState<EditingEntry | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [saving, setSaving] = useState(false)

  // UI state
  const [expandedTables, setExpandedTables] = useState<Set<string>>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('expandedTables')
      return saved ? new Set(JSON.parse(saved)) : new Set()
    }
    return new Set()
  })

  // AI-related state
  const [generatingGlobalAi, setGeneratingGlobalAi] = useState(false)
  const [showGlobalAiModal, setShowGlobalAiModal] = useState(false)
  const [currentAiJob, setCurrentAiJob] = useState<string | null>(null)
  const [aiJobProgress, setAiJobProgress] = useState<any>(null)
  const [aiJobs, setAiJobs] = useState<AIJob[]>([])
  const [selectedAiJob, setSelectedAiJob] = useState<AIJob | null>(null)

  // Create job form
  const [createFormData, setCreateFormData] = useState({
    business_domain: "",
    database_description: "",
    target_user: "",
    optional_notes: "",
    language: "persian"
  })

  // Load data on mount
  useEffect(() => {
    fetchSchemaSnapshots()
  }, [])

  // Auto-select first snapshot
  useEffect(() => {
    if (schemaSnapshots.length > 0 && !selectedSnapshot) {
      setSelectedSnapshot(schemaSnapshots[0])
    }
  }, [schemaSnapshots, selectedSnapshot])

  // Load data when snapshot changes
  useEffect(() => {
    if (selectedSnapshot) {
      fetchDataDictionary()
      fetchAiJobs()
    }
  }, [selectedSnapshot])

  // Restart polling for active jobs after page load/refresh
  // Use a ref to track if we've already set up polling to avoid loops
  const pollingSetupRef = useRef<Set<string>>(new Set())
  
  useEffect(() => {
    if (selectedSnapshot && aiJobs.length > 0) {
      // Find any processing or waiting jobs and restart polling
      const activeJobs = aiJobs.filter(job => 
        (job.status === 'processing' || job.status === 'waiting') &&
        !pollingSetupRef.current.has(job.job_id)
      )
      
      activeJobs.forEach(activeJob => {
        // Check if polling is already running for this job
        const existingInterval = (window as any)[`pollInterval_${activeJob.job_id}`]
        if (!existingInterval) {
          pollingSetupRef.current.add(activeJob.job_id)
          setCurrentAiJob(activeJob.job_id)
          startJobPolling(activeJob.job_id)
        }
      })
      
      // Clean up polling ref for completed/failed jobs
      aiJobs.forEach(job => {
        if (job.status === 'completed' || job.status === 'failed' || (job.status as string) === 'error') {
          pollingSetupRef.current.delete(job.job_id)
        }
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiJobs, selectedSnapshot])

  const fetchSchemaSnapshots = async () => {
    try {
      const response = await fetch("/api/schema/snapshots")
      if (response.ok) {
        const snapshots = await response.json()
        setSchemaSnapshots(snapshots)
      }
    } catch (error) {
      // Silently handle error - user will see empty list
    }
  }

  // Track last fetch to prevent duplicate calls
  const lastFetchRef = useRef<{ snapshotId: number | null, timestamp: number }>({ snapshotId: null, timestamp: 0 })
  
  const fetchDataDictionary = async () => {
    if (!selectedSnapshot) return

    // Prevent duplicate calls within 1 second for the same snapshot
    const now = Date.now()
    if (
      lastFetchRef.current.snapshotId === selectedSnapshot.id &&
      now - lastFetchRef.current.timestamp < 1000
    ) {
      return
    }

    lastFetchRef.current = { snapshotId: selectedSnapshot.id, timestamp: now }

    try {
      setLoading(true)
      const response = await fetch(`/api/data-dictionary?snapshot_id=${selectedSnapshot.id}`)

      if (response.ok) {
        const data = await response.json()
        setTableData(data.tables || [])
      } else {
        setTableData([])
      }
    } catch (error) {
      setTableData([])
    } finally {
      setLoading(false)
    }
  }

  const fetchAiJobs = async () => {
    if (!selectedSnapshot) return

    try {
      const response = await fetch(`/api/data-dictionary/ai-jobs?snapshot_id=${selectedSnapshot.id}`)
      if (response.ok) {
        const data = await response.json()
        setAiJobs(data.jobs || [])
      }
    } catch (error) {
      // Silently handle error
    }
  }

  const handleExportCSV = async () => {
    if (!selectedSnapshot) {
      toast({
        title: "Error",
        description: "Please select a snapshot first",
        variant: "destructive",
      })
      return
    }

    try {
      const response = await fetch(`/api/data-dictionary/export?snapshot_id=${selectedSnapshot.id}`)
      
      if (!response.ok) {
        throw new Error("Failed to export CSV")
      }

      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get("Content-Disposition")
      let filename = `data_dictionary_${selectedSnapshot.name}_${new Date().toISOString().split('T')[0]}.csv`
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Download file
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      toast({
        title: "Success",
        description: "Data dictionary exported successfully",
        variant: "default",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to export data dictionary",
        variant: "destructive",
      })
    }
  }

  // Simple AI generation for table
  const handleAiGenerate = async (schemaName: string, tableName: string, columnName?: string) => {
    try {
      const response = await fetch("/api/data-dictionary/table/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          snapshot_id: selectedSnapshot?.id,
          table_name: tableName,
          column_name: columnName,
          business_domain: "General",
          database_description: "Database",
          target_user: "Users"
        })
      })

      if (response.ok) {
        await fetchDataDictionary()
        toast({
          title: "Success",
          description: "AI generation completed",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate AI dictionary",
        variant: "destructive",
      })
    }
  }

  // Global AI generation for entire database
  const handleGlobalAiGeneration = () => {
    setShowGlobalAiModal(true)
  }

  const handleGlobalAiSubmit = async () => {
    if (!selectedSnapshot) return

    try {
      setGeneratingGlobalAi(true)

      // Start AI generation job
      const response = await fetch("/api/data-dictionary/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          snapshot_id: selectedSnapshot.id,
          business_domain: createFormData.business_domain,
          database_description: createFormData.database_description,
          target_user: createFormData.target_user,
          language: createFormData.language,
          additional_notes: createFormData.optional_notes
        })
      })

      if (response.ok) {
        const result = await response.json()
        const jobId = result.job_id

        if (jobId) {
          setCurrentAiJob(jobId)
          setShowGlobalAiModal(false)

          // Refresh jobs list to show new job
          await fetchAiJobs()

          // Start polling for job status
          startJobPolling(jobId)

          toast({
            title: "AI Generation Started",
            description: `Job ${jobId} started. Processing dictionary tables.`,
          })

          // Reset form
          setCreateFormData({
            business_domain: "",
            database_description: "",
            target_user: "",
            optional_notes: "",
            language: "persian"
          })
        } else {
          throw new Error("No job ID returned")
        }
      } else {
        let errorMessage = "AI generation failed"
        try {
          const error = await response.json()
          errorMessage = error.detail || errorMessage
        } catch (parseError) {
          const errorText = await response.text()
          errorMessage = `Server error (${response.status}): ${response.statusText}`
        }
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to start AI generation",
        variant: "destructive",
      })
    } finally {
      setGeneratingGlobalAi(false)
    }
  }

  const startJobPolling = (jobId: string) => {
    // Clear any existing polling for this job
    const existingInterval = (window as any)[`pollInterval_${jobId}`]
    if (existingInterval) {
      clearInterval(existingInterval)
    }

    let fetchJobsCounter = 0 // Counter to limit fetchAiJobs calls

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/data-dictionary/ai-generate/status/${jobId}`)
        if (response.ok) {
          const statusData = await response.json()
          setAiJobProgress(statusData)

          // Update aiJobs state directly with new status data
          setAiJobs(prevJobs => {
            return prevJobs.map(job => {
              if (job.job_id === jobId) {
                return {
                  ...job,
                  status: statusData.status,
                  completed_tables: statusData.completed_tables || job.completed_tables,
                  total_tables: statusData.total_tables || job.total_tables,
                  current_table: statusData.current_table,
                  progress: statusData.progress,
                  updated_at: new Date().toISOString()
                }
              }
              return job
            })
          })

          // Only fetch full jobs list every 10 seconds (every 5th poll) to avoid loop
          fetchJobsCounter++
          if (fetchJobsCounter >= 5 && selectedSnapshot) {
            fetchJobsCounter = 0
            await fetchAiJobs()
          }

          if (statusData.status === "completed" || statusData.status === "failed" || statusData.status === "error") {
            clearInterval(pollInterval)
            delete (window as any)[`pollInterval_${jobId}`]
            setGeneratingGlobalAi(false)
            setCurrentAiJob(null)
            // Refresh dictionary data
            await fetchDataDictionary()
            // Refresh jobs list one final time
            if (selectedSnapshot) {
              await fetchAiJobs()
            }
            toast({
              title: statusData.status === "completed" ? "AI Generation Complete" : "AI Generation Failed",
              description: statusData.message || "Process finished",
              variant: statusData.status === "completed" ? "default" : "destructive",
            })
          }
        } else {
          clearInterval(pollInterval)
          delete (window as any)[`pollInterval_${jobId}`]
          setGeneratingGlobalAi(false)
          setCurrentAiJob(null)
        }
      } catch (error) {
        clearInterval(pollInterval)
        delete (window as any)[`pollInterval_${jobId}`]
        setGeneratingGlobalAi(false)
        setCurrentAiJob(null)
      }
    }, 2000) // Poll every 2 seconds

    // Store interval reference
    ;(window as any)[`pollInterval_${jobId}`] = pollInterval
  }

  const handleAiJobAction = async (job: AIJob, action: 'start' | 'pause' | 'resume' | 'stop') => {
    try {
      let endpoint = ''
      const method = 'POST'

      switch (action) {
        case 'start':
          endpoint = `/api/data-dictionary/ai-jobs/${job.job_id}/start`
          break
        case 'pause':
          endpoint = `/api/data-dictionary/ai-jobs/${job.job_id}/pause`
          break
        case 'resume':
          endpoint = `/api/data-dictionary/ai-jobs/${job.job_id}/resume`
          break
        case 'stop':
          endpoint = `/api/data-dictionary/ai-jobs/${job.job_id}/stop`
          break
      }

      const response = await fetch(endpoint, { 
        method,
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const result = await response.json().catch(() => ({}))
        toast({
          title: "Success",
          description: result.message || `Job ${action}ed successfully`,
        })
        // Refresh jobs list immediately
        await fetchAiJobs()
        // If starting, also start polling for status updates
        if (action === 'start' || action === 'resume') {
          setCurrentAiJob(job.job_id)
          startJobPolling(job.job_id)
        }
        // If stopping or pausing, stop polling
        if (action === 'stop' || action === 'pause') {
          const pollInterval = (window as any)[`pollInterval_${job.job_id}`]
          if (pollInterval) {
            clearInterval(pollInterval)
            delete (window as any)[`pollInterval_${job.job_id}`]
          }
        }
      } else {
        let errorData: { detail?: string } = {}
        try {
          const text = await response.text()
          if (text && text.trim()) {
            try {
              errorData = JSON.parse(text)
            } catch (parseError) {
              // If JSON parsing fails, use the text as detail
              errorData = { detail: text || `Failed to ${action} job: ${response.status} ${response.statusText}` }
            }
          } else {
            errorData = { detail: `Failed to ${action} job: ${response.status} ${response.statusText}`             }
          }
        } catch (error) {
          errorData = { detail: `Failed to ${action} job: ${response.status} ${response.statusText}` }
        }
        toast({
          title: "Error",
          description: (errorData as { detail?: string; message?: string }).detail || (errorData as { detail?: string; message?: string }).message || `Failed to ${action} job (Status: ${response.status})`,
          variant: "destructive",
        })
      }
    } catch (error) {
      const errorMessage = error instanceof Error 
        ? error.message 
        : typeof error === 'string' 
          ? error 
          : 'An unexpected error occurred'
      
      toast({
        title: "Operation Failed",
        description: `Unable to ${action} the job. ${errorMessage}. Please try again or contact support if the problem persists.`,
        variant: "destructive",
      })
    }
  }

  const toggleTableExpansion = (tableKey: string) => {
    const newExpanded = new Set(expandedTables)
    if (newExpanded.has(tableKey)) {
      newExpanded.delete(tableKey)
    } else {
      newExpanded.add(tableKey)
    }
    setExpandedTables(newExpanded)
    if (typeof window !== 'undefined') {
      localStorage.setItem('expandedTables', JSON.stringify([...newExpanded]))
    }
  }

  const handleEditEntry = (schemaName: string, tableName: string, columnName?: string) => {
    // Find the table and column data
    const table = tableData.find(t => t.schema_name === schemaName && t.table_name === tableName)
    if (!table) return

    let description = ""
    let example_values = ""
    let synonyms = ""
    let is_sensitive = false

    if (columnName) {
      // Column-level editing
      const column = table.columns.find(c => c.name === columnName)
      if (column) {
        description = column.description || ""
        example_values = column.example_values?.join(", ") || ""
        // Only filter JSON (dict_needs) for AI-generated entries
        // Backend should handle this, but adding safety check here
        let synonymsRaw = column.synonyms || ""
        if (column.is_ai_generated && (synonymsRaw.trim().startsWith("{") || synonymsRaw.trim().startsWith("["))) {
          try {
            JSON.parse(synonymsRaw)
            synonyms = "" // It's JSON (dict_needs), not real synonyms
          } catch {
            synonyms = synonymsRaw // Not JSON, keep as is
          }
        } else {
          synonyms = synonymsRaw
        }
        is_sensitive = column.is_sensitive || false
      }
    } else {
      // Table-level editing
      description = table.description || ""
      example_values = table.example_values?.join(", ") || ""
      is_sensitive = table.is_sensitive || false
    }

    setEditingEntry({
      schema_name: schemaName,
      table_name: tableName,
      column_name: columnName,
      description,
      example_values,
      synonyms,
      is_sensitive
    })
    setShowEditDialog(true)
  }

  const handleSaveEntry = async () => {
    if (!editingEntry || !selectedSnapshot) return

    try {
      setSaving(true)

      // Parse example values
      const exampleValues = editingEntry.example_values
        .split(",")
        .map(v => v.trim())
        .filter(v => v.length > 0)

      const entryData = {
        schema_snapshot_id: selectedSnapshot.id,
        schema_name: editingEntry.schema_name,
        table_name: editingEntry.table_name,
        column_name: editingEntry.column_name || null,
        description: editingEntry.description || null,
        example_values: exampleValues.length > 0 ? exampleValues : null,
        synonyms: editingEntry.synonyms || null,
        is_sensitive: editingEntry.is_sensitive,
        is_ai_generated: false
      }

      // Try to create/update entry
      const response = await fetch("/api/data-dictionary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entryData)
        })

      if (response.ok) {
        await fetchDataDictionary()
        setShowEditDialog(false)
        setEditingEntry(null)
        toast({
          title: "Success",
          description: "Entry saved successfully",
        })
      } else {
        let errorMessage = "Failed to save"
        try {
          const error = await response.json()
          errorMessage = `Failed to save: ${error.detail || 'Unknown error'}`
        } catch (parseError) {
          const errorText = await response.text()
          errorMessage = `Server error (${response.status}): ${response.statusText}`
        }
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save entry",
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  if (schemaSnapshots.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Data Dictionary</h1>
          <p className="text-muted-foreground">
            Manage human-readable descriptions and metadata for your schema
          </p>
        </div>
        <EnhancedEmptyState
          icon={BookOpen}
          title="No Schema Snapshots"
          description="Create a schema snapshot first to view the data dictionary. A snapshot captures the current structure of your database schema."
          actions={{
            primary: {
              label: "Create Snapshot",
              onClick: () => router.push('/schema'),
              icon: Database
            }
          }}
          variant="card"
        />
      </div>
    )
  }

  if (loading || !selectedSnapshot) {
    return <PageLoader message="Loading data dictionary..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Data Dictionary</h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Manage human-readable descriptions and metadata for your schema
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <Label className="hidden sm:inline">Schema Snapshot:</Label>
            <Select
              value={selectedSnapshot?.id.toString() || ""}
              onValueChange={(value) => {
                const snapshot = schemaSnapshots.find(s => s.id.toString() === value)
                setSelectedSnapshot(snapshot || null)
              }}
            >
              <SelectTrigger className="w-full sm:w-64">
                <SelectValue placeholder="Select a snapshot" />
              </SelectTrigger>
              <SelectContent>
                {schemaSnapshots.map((snapshot) => (
                  <SelectItem key={snapshot.id} value={snapshot.id.toString()}>
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      {snapshot.name}
                      <Badge variant="outline" className="text-xs">
                        {snapshot.table_count} tables
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={() => fetchDataDictionary()}
              disabled={loading}
              className="flex items-center gap-2 flex-1 sm:flex-none"
              size="sm"
              title="Refresh data dictionary"
            >
              <Database className="h-4 w-4" />
              <span className="hidden sm:inline">Refresh</span>
              <span className="sm:hidden">Refresh</span>
            </Button>

            <Button
              onClick={handleExportCSV}
              disabled={loading || !selectedSnapshot}
              variant="outline"
              className="flex items-center gap-2 flex-1 sm:flex-none"
              size="sm"
              title="Export data dictionary to CSV"
            >
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline">Export CSV</span>
              <span className="sm:hidden">Export</span>
            </Button>

            <Button
              onClick={(e) => {
                e.preventDefault()
                handleGlobalAiGeneration()
              }}
              disabled={loading || !selectedSnapshot}
              className="flex items-center gap-2 flex-1 sm:flex-none"
              size="sm"
              title="Generate all descriptions using AI"
            >
              <Sparkles className="h-4 w-4" />
              <span className="hidden sm:inline">Generate All with AI</span>
              <span className="sm:hidden">AI Generate</span>
            </Button>
          </div>
        </div>
      </div>

      {selectedSnapshot && (
        <Tabs defaultValue="dictionary" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="dictionary" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Dictionary
            </TabsTrigger>
            <TabsTrigger value="ai-jobs" className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              AI Jobs ({aiJobs.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dictionary" className="space-y-4">
            {tableData.length === 0 ? (
              <EnhancedEmptyState
                icon={Database}
                title="No Data Dictionary Entries"
                description="No data dictionary entries found for this schema snapshot. You can generate descriptions using AI or add them manually."
                actions={{
                  primary: {
                    label: "Generate with AI",
                    onClick: handleGlobalAiGeneration,
                    icon: Sparkles
                  },
                  secondary: {
                    label: "Refresh",
                    onClick: fetchDataDictionary
                  }
                }}
              />
            ) : (
              tableData.map((table) => {
                const tableKey = `${table.schema_name}.${table.table_name}`
                const isExpanded = expandedTables.has(tableKey)

                return (
                  <Card key={tableKey}>
                    <CardHeader
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                      onClick={() => toggleTableExpansion(tableKey)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {isExpanded ? (
                            <ChevronDown className="h-5 w-5" />
                          ) : (
                            <ChevronRight className="h-5 w-5" />
                          )}
                          <Database className="h-5 w-5 text-blue-600" />
                          <div>
                            <CardTitle className="text-lg">{table.table_name}</CardTitle>
                            <CardDescription>{table.schema_name}</CardDescription>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{table.columns.length} columns</Badge>
                            {table.row_count && (
                            <Badge variant="secondary">{table.row_count.toLocaleString()} rows</Badge>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleEditEntry(table.schema_name, table.table_name)
                            }}
                            disabled={loading}
                            title="Edit table description"
                            className="flex items-center gap-1"
                          >
                            <Edit className="h-4 w-4" />
                            <span className="hidden sm:inline">Edit Table</span>
                            <span className="sm:hidden">Edit</span>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                                handleAiGenerate(table.schema_name, table.table_name)
                            }}
                              disabled={loading}
                              title="Generate description using AI"
                              className="flex items-center gap-1"
                          >
                              <Sparkles className="h-3 w-3" />
                              <span className="hidden sm:inline">AI</span>
                          </Button>
                        </div>
                      </div>
                      {table.description && (
                        <div className="mt-3 p-3 bg-muted/30 rounded-lg border">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <BookOpen className="h-4 w-4 text-blue-600" />
                                <span className="text-sm font-medium">Table Description</span>
                              {table.is_ai_generated && (
                                  <Badge variant="outline" className="text-xs">AI</Badge>
                              )}
                            </div>
                          </div>
                            <p className="text-sm text-muted-foreground">{table.description}</p>
                        </div>
                      )}
                    </CardHeader>

                    {isExpanded && (
                      <CardContent className="p-4">
                          {table.columns.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                              No columns found for this table
                            </div>
                          ) : (
                        <div className="border rounded-lg overflow-hidden">
                          <Table className="w-full">
                            <TableHeader>
                              <TableRow>
                                    <TableHead className="w-[20%]">Column</TableHead>
                                    <TableHead className="w-[15%]">Type</TableHead>
                                    <TableHead className="w-[10%]">Constraints</TableHead>
                                    <TableHead className="w-[30%]">Description</TableHead>
                                    <TableHead className="w-[15%]">Examples</TableHead>
                                    <TableHead className="w-[10%]">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                          <TableBody>
                            {table.columns.map((column) => (
                              <TableRow key={column.name}>
                                      <TableCell className="font-medium">{column.name}</TableCell>
                                      <TableCell className="font-mono text-sm">{column.type}</TableCell>
                                <TableCell>
                                        <div className="flex gap-1">
                                    {column.is_primary_key && (
                                      <Badge variant="default" className="text-xs">PK</Badge>
                                    )}
                                    {column.is_foreign_key && (
                                      <Badge variant="secondary" className="text-xs">FK</Badge>
                                    )}
                                  </div>
                                </TableCell>
                                <TableCell>
                                        <div className="space-y-1">
                                          <span className="text-sm">
                                      {column.description || <span className="text-muted-foreground">Not set</span>}
                                    </span>
                                    {column.is_ai_generated && (
                                            <Badge variant="outline" className="text-xs">AI</Badge>
                                    )}
                                  </div>
                                </TableCell>
                                <TableCell>
                                        <span className="text-sm">
                                      {column.example_values?.join(", ") || <span className="text-muted-foreground">Not set</span>}
                                    </span>
                                </TableCell>
                                <TableCell>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleEditEntry(table.schema_name, table.table_name, column.name)}
                                      disabled={loading}
                                      aria-label={`Edit column ${column.name}`}
                                      title={`Edit column ${column.name}`}
                                    >
                                        <Edit className="h-3 w-3" aria-hidden="true" />
                                    </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                          </Table>
                        </div>
                          )}
                      </CardContent>
                    )}
                  </Card>
                )
              })
                )}
          </TabsContent>

          <TabsContent value="ai-jobs" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {aiJobs.length === 0 ? (
                <div className="col-span-full">
                  <EnhancedEmptyState
                    icon={Sparkles}
                    title="No AI Jobs"
                    description="No AI generation jobs found for this snapshot. Create your first job to generate data dictionary entries automatically."
                    actions={{
                      primary: {
                        label: "Create First Job",
                        onClick: handleGlobalAiGeneration,
                        icon: Sparkles
                      }
                    }}
                    variant="card"
                  />
                </div>
              ) : (
                aiJobs.map((job) => (
                  <Card key={job.job_id} className="hover:shadow-md transition-shadow">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <Badge className={
                          job.status === "completed" ? "bg-green-100 text-green-800 border-green-200" :
                          job.status === "failed" ? "bg-red-100 text-red-800 border-red-200" :
                          job.status === "processing" ? "bg-blue-100 text-blue-800 border-blue-200" :
                          job.status === "paused" ? "bg-yellow-100 text-yellow-800 border-yellow-200" :
                          "bg-gray-100 text-gray-800 border-gray-200"
                        }>
                          <div className="flex items-center gap-1">
                            {job.status === "completed" && <CheckCircle className="h-4 w-4" />}
                            {job.status === "failed" && <AlertCircle className="h-4 w-4" />}
                            {job.status === "processing" && <Loader2 className="h-4 w-4 animate-spin" />}
                            {job.status === "paused" && <Pause className="h-4 w-4" />}
                            {job.status === "waiting" && <Clock className="h-4 w-4" />}
                            {job.status}
                          </div>
                        </Badge>
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {job.job_id.split('_').pop()}
                        </code>
                      </div>
                      <CardTitle className="text-lg">
                        {job.business_domain || 'AI Generation Job'}
                      </CardTitle>
                      <CardDescription>
                        Created {new Date(job.created_at).toLocaleString('en-US', { 
                          year: 'numeric', 
                          month: 'short', 
                          day: 'numeric', 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {/* Progress */}
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span>Progress</span>
                            <span>{job.completed_tables}/{job.total_tables} tables</span>
                          </div>
                          <Progress
                            value={(job.completed_tables / job.total_tables) * 100}
                            className="h-2"
                          />
                        </div>

                        {/* Current Table */}
                        {job.current_table && (
                          <div className="text-sm text-muted-foreground">
                            Processing: <code className="bg-muted px-1 rounded">{job.current_table}</code>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2">
                          {job.status === 'waiting' && (
                            <Button
                              size="sm"
                              onClick={() => handleAiJobAction(job, 'start')}
                              className="flex items-center gap-1"
                            >
                              <Play className="h-3 w-3" />
                              Start
                            </Button>
                          )}

                          {job.status === 'processing' && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleAiJobAction(job, 'pause')}
                                className="flex items-center gap-1"
                              >
                                <Pause className="h-3 w-3" />
                                Pause
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleAiJobAction(job, 'stop')}
                                className="flex items-center gap-1"
                              >
                                <Square className="h-3 w-3" />
                                Stop
                              </Button>
                            </>
                          )}

                          {job.status === 'paused' && (
                          <Button
                            size="sm"
                            onClick={() => handleAiJobAction(job, 'resume')}
                            className="flex items-center gap-1"
                          >
                            <Play className="h-3 w-3" />
                            Resume
                          </Button>
                          )}

                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setSelectedAiJob(job)}
                            className="flex items-center gap-1"
                          >
                            <BarChart3 className="h-3 w-3" />
                            Details
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </TabsContent>
        </Tabs>
      )}

      {/* AI Job Details Modal */}
      {selectedAiJob && (
        <Dialog open={!!selectedAiJob} onOpenChange={() => setSelectedAiJob(null)}>
          <DialogContent className="sm:max-w-[800px] max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Job Details: {selectedAiJob.job_id}
              </DialogTitle>
              <DialogDescription>
                {selectedAiJob.business_domain} • {selectedAiJob.language} • {selectedAiJob.target_user}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {/* Overall Progress */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Overall Progress</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <Progress
                      value={(selectedAiJob.completed_tables / selectedAiJob.total_tables) * 100}
                      className="w-full"
                    />
                    <div className="flex items-center justify-between text-sm">
                      <span>{selectedAiJob.completed_tables} of {selectedAiJob.total_tables} tables completed</span>
                      {selectedAiJob.current_table && (
                        <span className="text-muted-foreground">
                          Currently processing: <code>{selectedAiJob.current_table}</code>
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Job Information */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Job Information</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div><strong>Job ID:</strong> {selectedAiJob.job_id}</div>
                    <div><strong>Status:</strong> {selectedAiJob.status}</div>
                    <div><strong>Created:</strong> {new Date(selectedAiJob.created_at).toLocaleString('fa-IR')}</div>
                    <div><strong>Progress:</strong> {selectedAiJob.completed_tables}/{selectedAiJob.total_tables} tables</div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* AI Generation Progress - REMOVED: Only show job cards in AI Jobs tab, not duplicate progress indicator */}

      {/* Global AI Generation Modal */}
      <Dialog open={showGlobalAiModal} onOpenChange={setShowGlobalAiModal}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Generate Data Dictionary with AI</DialogTitle>
            <DialogDescription>
              Generate descriptions for all tables and columns in the entire database using AI.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="business-domain">Business Domain *</Label>
                <Input
                  id="business-domain"
                value={createFormData.business_domain}
                onChange={(e) => setCreateFormData({...createFormData, business_domain: e.target.value})}
                  placeholder="e.g., Retail, Healthcare, Finance"
                />
              </div>

            <div className="space-y-2">
              <Label htmlFor="database-description">Database Purpose *</Label>
                <Textarea
                  id="database-description"
                value={createFormData.database_description}
                onChange={(e) => setCreateFormData({...createFormData, database_description: e.target.value})}
                placeholder="What does this database represent?"
                rows={3}
                />
              </div>

            <div className="space-y-2">
              <Label htmlFor="target-user">Target Users *</Label>
                <Input
                  id="target-user"
                value={createFormData.target_user}
                onChange={(e) => setCreateFormData({...createFormData, target_user: e.target.value})}
                placeholder="e.g., Business Analysts, Data Scientists"
                />
              </div>

            <div className="space-y-2">
              <Label htmlFor="language">Language</Label>
                <Select
                value={createFormData.language}
                onValueChange={(value) => setCreateFormData({...createFormData, language: value})}
                >
                <SelectTrigger>
                  <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="persian">Persian (فارسی)</SelectItem>
                      <SelectItem value="english">English</SelectItem>
                    </SelectContent>
                  </Select>
              </div>

            <div className="space-y-2">
              <Label htmlFor="optional-notes">Additional Notes</Label>
              <Textarea
                id="optional-notes"
              value={createFormData.optional_notes}
              onChange={(e) => setCreateFormData({...createFormData, optional_notes: e.target.value})}
              placeholder="Any additional context"
              rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowGlobalAiModal(false)}
              disabled={generatingGlobalAi}
            >
              Cancel
            </Button>
            <Button
              onClick={handleGlobalAiSubmit}
              disabled={generatingGlobalAi || !createFormData.business_domain.trim() || !createFormData.database_description.trim() || !createFormData.target_user.trim()}
            >
              {generatingGlobalAi ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate with AI
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              Edit {editingEntry?.column_name ? "Column" : "Table"} Dictionary Entry
            </DialogTitle>
            <DialogDescription>
              {editingEntry?.column_name
                ? `Configure metadata for column "${editingEntry.column_name}"`
                : `Configure metadata for table "${editingEntry?.table_name}"`
              }
            </DialogDescription>
          </DialogHeader>

          {editingEntry && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSaveEntry()
              }}
              className="space-y-4 py-4"
            >
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                  value={editingEntry.description}
                    onChange={(e) => setEditingEntry(prev => prev ? {...prev, description: e.target.value} : null)}
                    placeholder="Human-readable description"
                  rows={3}
                />
            </div>

              {editingEntry.column_name && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="example-values">Example Values</Label>
                  <Input
                        id="example-values"
                      value={editingEntry.example_values}
                        onChange={(e) => setEditingEntry(prev => prev ? {...prev, example_values: e.target.value} : null)}
                        placeholder="value1, value2, value3"
                  />
                </div>

                  <div className="space-y-2">
                    <Label htmlFor="synonyms">Synonyms</Label>
                  <Input
                        id="synonyms"
                      value={editingEntry.synonyms}
                        onChange={(e) => setEditingEntry(prev => prev ? {...prev, synonyms: e.target.value} : null)}
                        placeholder="alias1, alias2, alias3"
                  />
                </div>
                </>
              )}

              <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id="sensitive"
                  checked={editingEntry.is_sensitive}
                          onChange={(e) => setEditingEntry(prev => prev ? {...prev, is_sensitive: e.target.checked} : null)}
                  className="rounded"
                        />
                <Label htmlFor="sensitive">Contains sensitive information</Label>
              </div>
            </form>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEditDialog(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleSaveEntry}
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}