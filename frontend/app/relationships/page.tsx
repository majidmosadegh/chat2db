"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { EmptyTable } from "@/components/ui/empty-state"
import { Link as LinkIcon } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import {
  Sparkles,
  ArrowRight,
  Loader2,
  Check,
  X,
  Edit,
  Trash2,
  Database,
  Table,
  Key,
  AlertCircle,
  Plus,
  BookOpen,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  Circle,
  Target
} from "lucide-react"
import { RelationshipCanvas } from "@/components/relationships/relationship-canvas"
import { PageLoader } from "@/components/ui/loading"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

// Table dimensions constants
const TABLE_WIDTH = 200
const TABLE_HEIGHT = 250

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  connection_id: number
  is_active: boolean
  created_at: string
  table_count: number
}

interface Relationship {
  id: number
  schema_snapshot_id: number
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship_type: "db_fk" | "ai_suggested" | "user_defined"
  join_type: "inner" | "left" | "right"
  cardinality: "1-1" | "1-n" | "n-1" | "n-n"
  description: string
  confidence_score?: number
  strength_score?: number
  semantic_similarity?: number
  user_accepted: boolean
  agent_approved: boolean
  is_confirmed: boolean
  created_at: string
  updated_at: string
}

interface AiSuggestedRelationship {
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship_type: "ai_suggested"
  join_type: "inner" | "left" | "right"
  cardinality: "1-1" | "1-n" | "n-1" | "n-n"
  description: string
  confidence_score: number
  reasoning: string
}

interface TableNode {
  id: string
  schema_name: string
  table_name: string
  row_count: number
  columns: Array<{
    name: string
    type: string
    is_primary_key: boolean
    is_foreign_key: boolean
  }>
  x: number
  y: number
}

export default function RelationshipsPage() {
  const { toast } = useToast()
  const [selectedSnapshot, setSelectedSnapshot] = useState<SchemaSnapshot | null>(null)
  const [schemaSnapshots, setSchemaSnapshots] = useState<SchemaSnapshot[]>([])
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [tableNodes, setTableNodes] = useState<TableNode[]>([])
  const [loading, setLoading] = useState(true)
  const [aiSuggesting, setAiSuggesting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Dialog states
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingRelationship, setEditingRelationship] = useState<Relationship | null>(null)
  const [showAiSuggestDialog, setShowAiSuggestDialog] = useState(false)
  const [aiBusinessContext, setAiBusinessContext] = useState("")
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [aiSuggestions, setAiSuggestions] = useState<AiSuggestedRelationship[]>([])
  const [showAiSuggestionsDialog, setShowAiSuggestionsDialog] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [resetCounter, setResetCounter] = useState(0)
  const [selectedRelationship, setSelectedRelationship] = useState<Relationship | null>(null)
  const [visibleTableCount, setVisibleTableCount] = useState(20) // Show first 20 tables by default
  const [autoFitTrigger, setAutoFitTrigger] = useState(0) // Trigger for auto-fit
  
  // Delete confirmation dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [relationshipToDelete, setRelationshipToDelete] = useState<number | null>(null)
  
  // Form validation errors
  const [createFormErrors, setCreateFormErrors] = useState<{
    source_table?: string
    source_column?: string
    target_table?: string
    target_column?: string
    description?: string
  }>({})
  const [editFormErrors, setEditFormErrors] = useState<{
    source_table?: string
    source_column?: string
    target_table?: string
    target_column?: string
    description?: string
  }>({})

  // Edit form state
  const [editForm, setEditForm] = useState<{
    source_table: string
    source_column: string
    target_table: string
    target_column: string
    relationship_type: "db_fk" | "ai_suggested" | "user_defined"
    join_type: "inner" | "left" | "right"
    cardinality: "1-1" | "1-n" | "n-1" | "n-n"
    description: string
    is_confirmed: boolean
  }>({
    source_table: "",
    source_column: "",
    target_table: "",
    target_column: "",
    relationship_type: "user_defined",
    join_type: "inner",
    cardinality: "1-n",
    description: "",
    is_confirmed: false
  })

  // Create form state
  const [createForm, setCreateForm] = useState<{
    source_table: string
    source_column: string
    target_table: string
    target_column: string
    relationship_type: "db_fk" | "ai_suggested" | "user_defined"
    join_type: "inner" | "left" | "right"
    cardinality: "1-1" | "1-n" | "n-1" | "n-n"
    description: string
    is_confirmed: boolean
  }>({
    source_table: "",
    source_column: "",
    target_table: "",
    target_column: "",
    relationship_type: "user_defined",
    join_type: "inner",
    cardinality: "1-n",
    description: "",
    is_confirmed: true
  })

  useEffect(() => {
    fetchSchemaSnapshots()
  }, [])

  useEffect(() => {
    if (selectedSnapshot) {
      loadData()
    } else {
      setRelationships([])
      setTableNodes([])
      setLoading(false)
    }
  }, [selectedSnapshot])

  // Handle escape key for fullscreen exit
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false)
      }
    }

    if (isFullscreen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden' // Prevent background scrolling
    } else {
      document.body.style.overflow = 'auto'
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'auto'
    }
  }, [isFullscreen])

  const fetchSchemaSnapshots = async () => {
    try {
      const response = await fetch("/api/schema/snapshots")
      if (response.ok) {
        const snapshots = await response.json()
        setSchemaSnapshots(snapshots)
        // Auto-select first snapshot if available
        if (snapshots.length > 0 && !selectedSnapshot) {
          setSelectedSnapshot(snapshots[0])
        }
      }
    } catch (error) {
    }
  }

  const loadData = async () => {
    if (!selectedSnapshot) return

    try {
      setLoading(true)
      setError(null)

      // Load relationships and schema data in parallel
      const [relationshipsRes, schemaRes] = await Promise.all([
        fetch(`/api/relationships/${selectedSnapshot.id}`),
        fetch(`/api/schema/tables?snapshot_id=${selectedSnapshot.id}`)
      ])

      if (relationshipsRes.ok) {
        const relationshipsData = await relationshipsRes.json()
        setRelationships(relationshipsData)
      }

      if (schemaRes.ok) {
        const schemaData = await schemaRes.json()

        // Limit initial visible tables for performance
        const visibleData = schemaData.slice(0, visibleTableCount)

        // Convert schema data to table nodes with improved positioning
        const nodes: TableNode[] = visibleData.map((table: any, index: number) => {
          // Calculate optimal grid based on number of tables
          const totalTables = visibleData.length
          const cols = Math.min(Math.max(Math.ceil(Math.sqrt(totalTables)), 3), 6) // 3-6 columns
          const rows = Math.ceil(totalTables / cols)

          // Spacing based on number of tables
          const baseSpacingX = 350 // Base horizontal spacing
          const baseSpacingY = 300 // Base vertical spacing (increased for more columns)

          const col = index % cols
          const row = Math.floor(index / cols)

          return {
            id: `${table.schema_name}.${table.table_name}`,
            schema_name: table.schema_name,
            table_name: table.table_name,
            row_count: table.row_count || 0,
            columns: table.columns || [],
            x: 150 + col * baseSpacingX,
            y: 150 + row * baseSpacingY
          }
        })
        setTableNodes(nodes)
      }

    } catch (err) {
      setError("Failed to load data")
    } finally {
      setLoading(false)
    }
  }

  const handleAiSuggest = async () => {
    if (!selectedSnapshot) {
      toast({
        title: "Warning",
        description: "Please select a schema snapshot first",
        variant: "warning",
      })
      return
    }

    try {
      setAiSuggesting(true)
      setError(null)

      const response = await fetch("/api/relationships/ai-suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_snapshot_id: selectedSnapshot.id,
          business_context: aiBusinessContext.trim() || undefined
        })
      })

      if (response.ok) {
        const data = await response.json()
        if (data.suggested_relationships && data.suggested_relationships.length > 0) {
          setAiSuggestions(data.suggested_relationships)
          setShowAiSuggestionsDialog(true)
        } else {
          toast({
            title: "No Suggestions",
            description: "AI found no relationship suggestions for your schema.",
            variant: "warning",
          })
        }
        setShowAiSuggestDialog(false)
        setAiBusinessContext("")
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "AI suggestion failed")
      }
    } catch (err) {
      setError("Failed to get AI suggestions")
    } finally {
      setAiSuggesting(false)
    }
  }

  const handleEditRelationship = (relationship: Relationship) => {
    // Ensure all values are strings and have valid defaults
    const safeRelationshipType = relationship.relationship_type || 'user_defined'
    const safeJoinType = relationship.join_type || 'inner'
    const safeCardinality = relationship.cardinality || '1-n'

    // Find matching table nodes - try different formats
    let sourceTableNode = tableNodes.find(t => t.id === relationship.source_table)
    let targetTableNode = tableNodes.find(t => t.id === relationship.target_table)

    // If not found, try with schema prefix
    if (!sourceTableNode && selectedSnapshot) {
      sourceTableNode = tableNodes.find(t => t.id === `${selectedSnapshot.name}.${relationship.source_table}`)
    }
    if (!targetTableNode && selectedSnapshot) {
      targetTableNode = tableNodes.find(t => t.id === `${selectedSnapshot.name}.${relationship.target_table}`)
    }

    // If still not found, try just table name
    if (!sourceTableNode) {
      sourceTableNode = tableNodes.find(t => t.table_name === relationship.source_table)
    }
    if (!targetTableNode) {
      targetTableNode = tableNodes.find(t => t.table_name === relationship.target_table)
    }

    setEditingRelationship(relationship)
    setEditForm({
      source_table: sourceTableNode ? sourceTableNode.id : '',
      source_column: sourceTableNode ? relationship.source_column : '',
      target_table: targetTableNode ? targetTableNode.id : '',
      target_column: targetTableNode ? relationship.target_column : '',
      relationship_type: safeRelationshipType,
      join_type: safeJoinType,
      cardinality: safeCardinality,
      description: relationship.description,
      is_confirmed: relationship.is_confirmed
    })
    setShowEditDialog(true)
  }

  const handleSaveRelationship = async () => {
    if (!editingRelationship) return

    try {
      const response = await fetch(`/api/relationships/${editingRelationship.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editForm)
      })

      if (response.ok) {
        setShowEditDialog(false)
        setEditingRelationship(null)
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to save relationship")
      }
    } catch (err) {
      setError("Failed to save relationship")
    }
  }

  const handleDeleteRelationship = (relationshipId: number) => {
    setRelationshipToDelete(relationshipId)
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!relationshipToDelete) return

    try {
      const response = await fetch(`/api/relationships/${relationshipToDelete}`, {
        method: "DELETE"
      })

      if (response.ok) {
        await loadData()
        toast({
          title: "Success",
          description: "Relationship deleted successfully",
        })
      } else {
        const errorData = await response.json()
        toast({
          title: "Error",
          description: errorData.detail || "Failed to delete relationship",
          variant: "destructive",
        })
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete relationship",
        variant: "destructive",
      })
    } finally {
      setShowDeleteDialog(false)
      setRelationshipToDelete(null)
    }
  }

  const handleAcceptAiSuggestion = async (relationship: Relationship) => {
    try {
      const response = await fetch(`/api/relationships/${relationship.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...relationship,
          is_confirmed: true
        })
      })

      if (response.ok) {
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to accept relationship")
      }
    } catch (err) {
      setError("Failed to accept relationship")
    }
  }

  const handleAcceptAllAiSuggestions = async () => {
    if (!selectedSnapshot) {
      toast({
        title: "Warning",
        description: "Please select a schema snapshot first",
        variant: "warning",
      })
      return
    }

    try {
      setAiSuggesting(true)
      const response = await fetch("/api/relationships/ai-suggest/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          suggestions: aiSuggestions,
          snapshot_id: selectedSnapshot.id
        })
      })

      if (response.ok) {
        const data = await response.json()
        toast({
          title: "Success",
          description: data.message,
          variant: "success",
        })
        setShowAiSuggestionsDialog(false)
        setAiSuggestions([])
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to accept AI suggestions")
      }
    } catch (err) {
      setError("Failed to accept AI suggestions")
    } finally {
      setAiSuggesting(false)
    }
  }

  const handleOpenCreateRelationshipModal = (sourceTable: string, sourceColumn: string) => {
    setCreateForm({
      source_table: sourceTable,
      source_column: sourceColumn,
      target_table: "",
      target_column: "",
      relationship_type: "user_defined",
      join_type: "inner",
      cardinality: "1-n",
      description: "",
      is_confirmed: true
    })
    setShowCreateDialog(true)
  }

  const handleDragCreateRelationship = (sourceTable: string, sourceColumn: string, targetTable: string, targetColumn: string) => {
    toast({
      title: "Creating Relationship",
      description: `Creating relationship: ${sourceTable}.${sourceColumn} -> ${targetTable}.${targetColumn}`,
      variant: "default",
    })
    setCreateForm({
      source_table: sourceTable,
      source_column: sourceColumn,
      target_table: targetTable,
      target_column: targetColumn,
      relationship_type: "user_defined",
      join_type: "inner",
      cardinality: "1-n",
      description: `Relationship between ${sourceTable}.${sourceColumn} and ${targetTable}.${targetColumn}`,
      is_confirmed: true
    })
    setShowCreateDialog(true)
  }

  const handleTableMove = (tableId: string, newX: number, newY: number) => {
    setTableNodes(prevNodes =>
      prevNodes.map(node =>
        node.id === tableId
          ? { 
              ...node, 
              // در fullscreen محدودیت را برمی‌داریم تا جدول‌ها بتوانند آزادانه حرکت کنند
              x: isFullscreen ? newX : Math.max(0, newX), 
              y: isFullscreen ? newY : Math.max(0, newY) 
            }
          : node
      )
    )
  }

  const handleFullscreenToggle = () => {
    setIsFullscreen(!isFullscreen)
  }

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.2, 3)) // حداکثر زوم 3 برابر
  }

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.2, 0.3)) // حداقل زوم 0.3 برابر
  }

  const handleZoomReset = () => {
    setZoomLevel(1)
  }

  const handlePanReset = () => {
    // Increment reset counter to trigger canvas reset
    setResetCounter(prev => prev + 1)
  }

  const handleSmartLayout = () => {
    if (tableNodes.length === 0) return

    // Smart layout algorithm
    const centerX = 700 // Canvas center X
    const centerY = 500 // Canvas center Y
    const radius = Math.min(600, 300 + tableNodes.length * 20) // Adaptive radius

    const newNodes = tableNodes.map((node, index) => {
      const angle = (index / tableNodes.length) * 2 * Math.PI

      // Add some randomness to prevent perfect circles
      const randomOffset = (Math.random() - 0.5) * 100
      const distance = radius + randomOffset

      return {
        ...node,
        x: centerX + Math.cos(angle) * distance - TABLE_WIDTH / 2,
        y: centerY + Math.sin(angle) * distance - TABLE_HEIGHT / 2
      }
    })

    setTableNodes(newNodes)
    // Auto-fit after layout
    setTimeout(() => {
      setResetCounter(prev => prev + 1)
    }, 100)
  }

  const handleFormCreateRelationship = async () => {
    if (!selectedSnapshot) {
      toast({
        title: "Warning",
        description: "Please select a schema snapshot first",
        variant: "warning",
      })
      return
    }

    // Validate required fields with detailed errors
    const errors: typeof createFormErrors = {}
    if (!createForm.source_table) {
      errors.source_table = "Source table is required"
    }
    if (!createForm.source_column) {
      errors.source_column = "Source column is required"
    }
    if (!createForm.target_table) {
      errors.target_table = "Target table is required"
    }
    if (!createForm.target_column) {
      errors.target_column = "Target column is required"
    }
    if (!createForm.description.trim()) {
      errors.description = "Description is required"
    }

    if (Object.keys(errors).length > 0) {
      setCreateFormErrors(errors)
      setError("Please fill in all required fields")
      return
    }

    setCreateFormErrors({})
    setError(null)

    try {
      const response = await fetch("/api/relationships", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_snapshot_id: selectedSnapshot.id,
          ...createForm
        })
      })

      if (response.ok) {
        setShowCreateDialog(false)
        setCreateForm({
          source_table: "",
          source_column: "",
          target_table: "",
          target_column: "",
          relationship_type: "user_defined",
          join_type: "inner",
          cardinality: "1-n",
          description: "",
          is_confirmed: true
        })
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to create relationship")
      }
    } catch (err) {
      setError("Failed to create relationship")
    }
  }

  return (
    <div className={`space-y-6 ${isFullscreen ? 'overflow-hidden' : ''}`}>
      <div className={`flex flex-col lg:flex-row lg:items-center justify-between gap-4 ${isFullscreen ? 'hidden' : ''}`}>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold">Schema Relationships</h1>
          <p className="text-muted-foreground text-sm md:text-base">
            Manage relationships for your schema snapshots
          </p>
        </div>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
            <div className="flex items-center gap-2 w-full sm:w-auto min-w-0">
              <Label className="text-sm whitespace-nowrap flex-shrink-0">Schema Snapshot:</Label>
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
                        <span className="truncate">{snapshot.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {snapshot.table_count} tables
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {selectedSnapshot && (
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => setShowCreateDialog(true)}
                variant="outline"
                className="flex items-center gap-2 justify-center flex-1 sm:flex-none"
                size="sm"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Create Relationship</span>
                <span className="sm:hidden">Create</span>
              </Button>
              <Button
                onClick={() => setShowAiSuggestDialog(true)}
                disabled={aiSuggesting}
                className="flex items-center gap-2 justify-center flex-1 sm:flex-none"
                size="sm"
              >
                {aiSuggesting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                <span className="hidden sm:inline">
                  {aiSuggesting ? "Suggesting..." : "Suggest Relationships"}
                </span>
                <span className="sm:hidden">
                  {aiSuggesting ? "..." : "Suggest"}
                </span>
              </Button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {loading ? (
        <PageLoader message="Loading relationships..." />
      ) : !selectedSnapshot ? (
        <div className="text-center py-12">
          <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-medium mb-2">No Schema Snapshot Selected</h3>
          <p className="text-muted-foreground mb-4">
            Please select a schema snapshot from the dropdown above to view and manage relationships.
          </p>
          {schemaSnapshots.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No schema snapshots found. Please create a schema snapshot first.
            </p>
          )}
        </div>
      ) : (
        <>
          {/* Fullscreen Overlay */}
          {isFullscreen && (
            <div 
              className="fixed inset-0 bg-black bg-opacity-50 z-40" 
              onClick={handleFullscreenToggle}
              style={{ pointerEvents: 'auto' }}
            />
          )}

                  {/* Load More Tables Button */}
                  {selectedSnapshot && tableNodes.length >= visibleTableCount && (
                    <div className="mb-4 flex justify-center">
                      <Button
                        onClick={async () => {
                          const newCount = visibleTableCount + 20
                          setVisibleTableCount(newCount)

                          // Reload with more tables
                          const schemaRes = await fetch(`/api/schema/tables?snapshot_id=${selectedSnapshot.id}`)
                          if (schemaRes.ok) {
                            const schemaData = await schemaRes.json()
                            const visibleData = schemaData.slice(0, newCount)

                            const nodes: TableNode[] = visibleData.map((table: any, index: number) => {
                              const totalTables = visibleData.length
                              const cols = Math.min(Math.max(Math.ceil(Math.sqrt(totalTables)), 3), 6)
                              const rows = Math.ceil(totalTables / cols)

                              const baseSpacingX = 350
                              const baseSpacingY = 300

                              const col = index % cols
                              const row = Math.floor(index / cols)

                              return {
                                id: `${table.schema_name}.${table.table_name}`,
                                schema_name: table.schema_name,
                                table_name: table.table_name,
                                columns: table.columns || [],
                                x: 150 + col * baseSpacingX,
                                y: 150 + row * baseSpacingY
                              }
                            })
                            setTableNodes(nodes)
                          }
                        }}
                        variant="outline"
                        className="w-full sm:w-auto"
                      >
                        Load More Tables ({tableNodes.length} shown)
                      </Button>
                    </div>
                  )}

                  {/* Visual Canvas */}
                  <Card 
                    className={isFullscreen ? "fixed inset-0 sm:inset-4 z-50 rounded-none sm:rounded-lg bg-white dark:bg-gray-900 flex flex-col" : ""}
                    style={isFullscreen ? { pointerEvents: 'auto' } : {}}
                  >
            <CardHeader className={`${isFullscreen ? 'flex flex-col sm:flex-row sm:items-center justify-between space-y-2 sm:space-y-0 pb-2 gap-4 flex-shrink-0' : 'flex flex-col sm:flex-row sm:items-center justify-between space-y-2 sm:space-y-0 pb-2 gap-4'}`}>
              <div className="flex-1 min-w-0">
                <CardTitle className={`${isFullscreen ? 'text-lg sm:text-xl' : 'text-lg sm:text-xl'}`}>Relationship Diagram</CardTitle>
                {!isFullscreen && (
                  <CardDescription className="text-sm">
                    Visual representation of tables and their relationships.
                    <br />
                    <small className="text-muted-foreground block mt-1">
                      • Drag column to column to create relationships
                      • Hold SPACE + mouse to pan the canvas
                      • Use zoom controls to adjust view
                      • Multiple relationships are automatically bundled and layered
                      • [1], [2] etc. show relationship layers between same tables
                    </small>
                  </CardDescription>
                )}
              </div>
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    Zoom: {Math.round(zoomLevel * 100)}%
                  </span>
                  <div className="flex flex-wrap gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleZoomOut}
                      disabled={zoomLevel <= 0.3}
                      title="Zoom Out"
                      className="flex-shrink-0"
                    >
                      <ZoomOut className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleZoomReset}
                      title="Reset Zoom"
                      className="flex-shrink-0"
                    >
                      <span className="text-xs hidden sm:inline">Reset</span>
                      <span className="text-xs sm:hidden">R</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleZoomIn}
                      disabled={zoomLevel >= 3}
                      title="Zoom In"
                      className="flex-shrink-0"
                    >
                      <ZoomIn className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handlePanReset}
                      title="Reset Pan & Zoom"
                      className="flex-shrink-0"
                    >
                      🔄
                    </Button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSmartLayout}
                    title="Smart circular layout"
                    disabled={tableNodes.length < 3}
                    className="hidden sm:flex flex-shrink-0"
                  >
                    <Circle className="h-4 w-4 mr-1" />
                    <span className="hidden md:inline">Layout</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (tableNodes.length > 0) {
                        // Calculate zoom to fit all tables
                        const minX = Math.min(...tableNodes.map(n => n.x))
                        const minY = Math.min(...tableNodes.map(n => n.y))
                        const maxX = Math.max(...tableNodes.map(n => n.x + 200)) // TABLE_WIDTH approx
                        const maxY = Math.max(...tableNodes.map(n => n.y + 250)) // TABLE_HEIGHT approx

                        const contentWidth = maxX - minX
                        const contentHeight = maxY - minY

                        // Calculate zoom to fit content in viewport
                        const zoomX = 1400 / contentWidth
                        const zoomY = 1000 / contentHeight
                        const optimalZoom = Math.min(zoomX, zoomY, 1)

                        setZoomLevel(optimalZoom)

                        // Trigger auto-fit to center content
                        setAutoFitTrigger(prev => prev + 1)
                      }
                    }}
                    title="Auto-fit all tables"
                    disabled={tableNodes.length === 0}
                    className="hidden md:flex flex-shrink-0"
                  >
                    <Target className="h-4 w-4 mr-1" />
                    Fit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleFullscreenToggle}
                    title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
                    className="flex-shrink-0"
                  >
                    {isFullscreen ? (
                      <Minimize2 className="h-4 w-4" />
                    ) : (
                      <Maximize2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {isFullscreen && (
                  <span className="text-xs text-muted-foreground self-center sm:self-end">
                    Press ESC to exit
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className={`${isFullscreen ? "flex-1 min-h-0 p-0 overflow-hidden flex flex-col" : ""}`}>
              {tableNodes.length === 0 ? (
                <div className="h-64 sm:h-96 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center">
                  <div className="text-center text-muted-foreground px-4">
                    <Database className="h-8 w-8 sm:h-12 sm:w-12 mx-auto mb-4 opacity-50" />
                    <p className="text-sm sm:text-base">No tables loaded.</p>
                    <p className="text-xs sm:text-sm">Make sure schema introspection has been run.</p>
                  </div>
                </div>
              ) : (
                <div className={`${isFullscreen ? "flex-1 min-h-0 w-full overflow-hidden" : ""}`}>
                  <RelationshipCanvas
                    tableNodes={tableNodes}
                    relationships={relationships}
                    onEditRelationship={handleEditRelationship}
                    onDeleteRelationship={handleDeleteRelationship}
                    onAcceptRelationship={handleAcceptAiSuggestion}
                    onCreateRelationship={handleDragCreateRelationship}
                    onOpenCreateRelationshipModal={handleOpenCreateRelationshipModal}
                    onTableMove={handleTableMove}
                    resetTrigger={resetCounter}
                    zoomLevel={zoomLevel}
                    isFullscreen={isFullscreen}
                    cleanMode={false}
                    onRelationshipClick={(relationship) => setSelectedRelationship(relationship)}
                    autoFitTrigger={autoFitTrigger}
                  />
                  {relationships.length === 0 && !isFullscreen && (
                    <div className="mt-4 p-3 sm:p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                      <div className="flex items-center gap-2 text-blue-800 dark:text-blue-200">
                        <Plus className="h-4 w-4 sm:h-5 sm:w-5" />
                        <span className="font-medium text-sm sm:text-base">Getting Started</span>
                      </div>
                      <p className="mt-2 text-xs sm:text-sm text-blue-700 dark:text-blue-300">
                        No relationships found. Use the "Create Relationship" button to manually define relationships,
                        drag from one column to another on the diagram above, or try "Suggest Relationships" to let AI discover them automatically.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Relationships List */}
          <Card className={isFullscreen ? "hidden" : ""}>
            <CardHeader>
              <CardTitle>Relationships ({relationships.length})</CardTitle>
              <CardDescription>
                All relationships in this schema snapshot
              </CardDescription>
            </CardHeader>
            <CardContent>
              {relationships.length === 0 ? (
                <EmptyTable
                  icon={LinkIcon}
                  title="No relationships defined"
                  description="Start by creating relationships between your database tables. You can create them manually or get AI-powered suggestions."
                  action={{
                    label: "Create First Relationship",
                    onClick: () => setShowCreateDialog(true)
                  }}
                />
              ) : (
                <div className="space-y-4">
                  {relationships.map((rel) => (
                    <div key={rel.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-2">
                            <Badge variant={
                              rel.relationship_type === "db_fk" ? "default" :
                              rel.relationship_type === "ai_suggested" ? "secondary" : "outline"
                            }>
                              {rel.relationship_type === "db_fk" ? "DB FK" :
                               rel.relationship_type === "ai_suggested" ? "AI Suggested" : "User Defined"}
                            </Badge>
                            {rel.confidence_score && (
                              <Badge variant="outline">
                                {Math.round(rel.confidence_score * 100)}% confidence
                              </Badge>
                            )}
                            {!rel.is_confirmed && rel.relationship_type === "ai_suggested" && (
                              <Badge variant="destructive">Unconfirmed</Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditRelationship(rel)}
                            aria-label={`Edit relationship ${rel.source_table}.${rel.source_column} → ${rel.target_table}.${rel.target_column}`}
                            title={`Edit relationship`}
                          >
                            <Edit className="h-4 w-4" aria-hidden="true" />
                          </Button>
                          {rel.relationship_type !== "db_fk" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteRelationship(rel.id)}
                              aria-label={`Delete relationship ${rel.source_table}.${rel.source_column} → ${rel.target_table}.${rel.target_column}`}
                              title={`Delete relationship`}
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          )}
                          {rel.relationship_type === "ai_suggested" && !rel.is_confirmed && (
                            <Button
                              size="sm"
                              onClick={() => handleAcceptAiSuggestion(rel)}
                              className="flex items-center gap-1"
                            >
                              <Check className="h-4 w-4" />
                              Accept
                            </Button>
                          )}
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">Source</div>
                          <div className="font-mono text-sm break-all">
                            {rel.source_table}.{rel.source_column}
                          </div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">Target</div>
                          <div className="font-mono text-sm break-all">
                            {rel.target_table}.{rel.target_column}
                          </div>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-2 sm:gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <span className="text-muted-foreground">Join:</span>
                          <span className="font-medium">{rel.join_type}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-muted-foreground">Cardinality:</span>
                          <span className="font-medium">{rel.cardinality}</span>
                        </div>
                      </div>

                      <div className="mt-3">
                        <div className="text-sm font-medium text-muted-foreground">Description</div>
                        <div className="text-sm">{rel.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Create Relationship Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="w-[95vw] sm:w-[600px] max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">Create New Relationship</DialogTitle>
            <DialogDescription className="text-sm">
              Manually create a relationship between two tables in your schema.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleFormCreateRelationship()
            }}
          >
          <div className="grid gap-3 sm:gap-4 py-2 sm:py-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-source-table">
                  Source Table *
                </Label>
                <Select
                  value={createForm.source_table}
                  onValueChange={(value) => {
                    setCreateForm(prev => ({
                      ...prev,
                      source_table: value,
                      source_column: "" // Reset column when table changes
                    }))
                    if (createFormErrors.source_table) {
                      setCreateFormErrors(prev => ({ ...prev, source_table: undefined }))
                    }
                  }}
                >
                  <SelectTrigger className={createFormErrors.source_table ? "border-destructive" : ""}>
                    <SelectValue placeholder="Select source table" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes.map((table) => (
                      <SelectItem key={table.id} value={table.id}>
                        {table.table_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {createFormErrors.source_table && (
                  <p className="text-sm text-destructive">{createFormErrors.source_table}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-target-table">
                  Target Table *
                </Label>
                <Select
                  value={createForm.target_table}
                  onValueChange={(value) => {
                    setCreateForm(prev => ({
                      ...prev,
                      target_table: value,
                      target_column: "" // Reset column when table changes
                    }))
                    if (createFormErrors.target_table) {
                      setCreateFormErrors(prev => ({ ...prev, target_table: undefined }))
                    }
                  }}
                >
                  <SelectTrigger className={createFormErrors.target_table ? "border-destructive" : ""}>
                    <SelectValue placeholder="Select target table" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes.map((table) => (
                      <SelectItem key={table.id} value={table.id}>
                        {table.table_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {createFormErrors.target_table && (
                  <p className="text-sm text-destructive">{createFormErrors.target_table}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-source-column">
                  Source Column *
                </Label>
                <Select
                  value={createForm.source_column}
                  onValueChange={(value) => {
                    setCreateForm(prev => ({ ...prev, source_column: value }))
                    if (createFormErrors.source_column) {
                      setCreateFormErrors(prev => ({ ...prev, source_column: undefined }))
                    }
                  }}
                  disabled={!createForm.source_table}
                >
                  <SelectTrigger className={createFormErrors.source_column ? "border-destructive" : ""}>
                    <SelectValue placeholder="Select source column" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes
                      .find(t => t.id === createForm.source_table)
                      ?.columns.map((column) => (
                        <SelectItem key={column.name} value={column.name}>
                          {column.name} ({column.type})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
                {createFormErrors.source_column && (
                  <p className="text-sm text-destructive">{createFormErrors.source_column}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-target-column">
                  Target Column *
                </Label>
                <Select
                  value={createForm.target_column}
                  onValueChange={(value) => {
                    setCreateForm(prev => ({ ...prev, target_column: value }))
                    if (createFormErrors.target_column) {
                      setCreateFormErrors(prev => ({ ...prev, target_column: undefined }))
                    }
                  }}
                  disabled={!createForm.target_table}
                >
                  <SelectTrigger className={createFormErrors.target_column ? "border-destructive" : ""}>
                    <SelectValue placeholder="Select target column" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes
                      .find(t => t.id === createForm.target_table)
                      ?.columns.map((column) => (
                        <SelectItem key={column.name} value={column.name}>
                          {column.name} ({column.type})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-join-type">
                  Join Type
                </Label>
                <Select
                  value={createForm.join_type}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, join_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inner">Inner</SelectItem>
                    <SelectItem value="left">Left</SelectItem>
                    <SelectItem value="right">Right</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-cardinality">
                  Cardinality
                </Label>
                <Select
                  value={createForm.cardinality}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, cardinality: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1-1">1-1</SelectItem>
                    <SelectItem value="1-n">1-n</SelectItem>
                    <SelectItem value="n-1">n-1</SelectItem>
                    <SelectItem value="n-n">n-n</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-relationship-type">
                  Type
                </Label>
                <Select
                  value={createForm.relationship_type}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, relationship_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user_defined">User Defined</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-description">
                Description *
              </Label>
              <Textarea
                id="create-description"
                value={createForm.description}
                onChange={(e) => {
                  setCreateForm(prev => ({ ...prev, description: e.target.value }))
                  if (createFormErrors.description) {
                    setCreateFormErrors(prev => ({ ...prev, description: undefined }))
                  }
                }}
                placeholder="Describe this relationship..."
                rows={3}
                className={createFormErrors.description ? "border-destructive" : ""}
              />
              {createFormErrors.description && (
                <p className="text-sm text-destructive">{createFormErrors.description}</p>
              )}
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
              className="w-full sm:w-auto order-2 sm:order-1"
            >
              Cancel
            </Button>
            <Button type="submit" onClick={handleFormCreateRelationship} className="w-full sm:w-auto order-1 sm:order-2">
              Create Relationship
            </Button>
          </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AI Suggest Dialog */}
      <Dialog open={showAiSuggestDialog} onOpenChange={setShowAiSuggestDialog}>
        <DialogContent className="w-[90vw] sm:w-[500px] max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">Get AI Relationship Suggestions</DialogTitle>
            <DialogDescription className="text-sm">
              Use AI to automatically discover logical relationships in your schema.
              Provide business context to get more relevant suggestions.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-start gap-4">
              <Label htmlFor="business-context" className="text-right pt-2">
                Business Context
              </Label>
              <Textarea
                id="business-context"
                value={aiBusinessContext}
                onChange={(e) => setAiBusinessContext(e.target.value)}
                placeholder="e.g., This is an e-commerce database for an online store selling products to customers..."
                className="col-span-3"
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAiSuggestDialog(false)}
              disabled={aiSuggesting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAiSuggest}
              disabled={aiSuggesting}
            >
              {aiSuggesting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Getting Suggestions...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Get Suggestions
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Relationship Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => {
        setShowEditDialog(open)
        if (!open) {
          setEditingRelationship(null)
        }
      }}>
        <DialogContent className="w-[95vw] sm:w-[600px] max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">Edit Relationship</DialogTitle>
            <DialogDescription className="text-sm">
              Modify the relationship properties.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:gap-4 py-2 sm:py-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="source-table">
                  Source Table
                </Label>
                <Select
                  key={`source-table-${editForm.source_table}`}
                  value={editForm.source_table}
                  onValueChange={(value: any) => setEditForm(prev => ({
                    ...prev,
                    source_table: value,
                    source_column: "" // Reset column when table changes
                  }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select source table" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes.map((table) => (
                      <SelectItem key={table.id} value={table.id}>
                        {table.table_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-table">
                  Target Table
                </Label>
                <Select
                  key={`target-table-${editForm.target_table}`}
                  value={editForm.target_table}
                  onValueChange={(value: any) => setEditForm(prev => ({
                    ...prev,
                    target_table: value,
                    target_column: "" // Reset column when table changes
                  }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select target table" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes.map((table) => (
                      <SelectItem key={table.id} value={table.id}>
                        {table.table_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {createFormErrors.target_table && (
                  <p className="text-sm text-destructive">{createFormErrors.target_table}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="source-column">
                  Source Column
                </Label>
                <Select
                  key={`source-column-${editForm.source_table}-${editForm.source_column}`}
                  value={editForm.source_column}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, source_column: value }))}
                  disabled={!editForm.source_table}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select source column" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes
                      .find(t => t.id === editForm.source_table)
                      ?.columns.map((column) => (
                        <SelectItem key={column.name} value={column.name}>
                          {column.name} ({column.type})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-column">
                  Target Column
                </Label>
                <Select
                  key={`target-column-${editForm.target_table}-${editForm.target_column}`}
                  value={editForm.target_column}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, target_column: value }))}
                  disabled={!editForm.target_table}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select target column" />
                  </SelectTrigger>
                  <SelectContent>
                    {tableNodes
                      .find(t => t.id === editForm.target_table)
                      ?.columns.map((column) => (
                        <SelectItem key={column.name} value={column.name}>
                          {column.name} ({column.type})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="join-type">
                  Join Type
                </Label>
                <Select
                  key={`join-type-${editForm.join_type}`}
                  value={editForm.join_type}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, join_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select join type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inner">Inner</SelectItem>
                    <SelectItem value="left">Left</SelectItem>
                    <SelectItem value="right">Right</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="cardinality">
                  Cardinality
                </Label>
                <Select
                  key={`cardinality-${editForm.cardinality}`}
                  value={editForm.cardinality}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, cardinality: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select cardinality" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1-1">1-1</SelectItem>
                    <SelectItem value="1-n">1-n</SelectItem>
                    <SelectItem value="n-1">n-1</SelectItem>
                    <SelectItem value="n-n">n-n</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="relationship-type">
                  Type
                </Label>
                <Select
                  key={`relationship-type-${editForm.relationship_type}`}
                  value={editForm.relationship_type}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, relationship_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select relationship type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user_defined">User Defined</SelectItem>
                    <SelectItem value="ai_suggested">AI Suggested</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">
                Description
              </Label>
              <Textarea
                id="description"
                value={editForm.description}
                onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                rows={3}
              />
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="is-confirmed"
                checked={editForm.is_confirmed}
                onChange={(e) => setEditForm(prev => ({ ...prev, is_confirmed: e.target.checked }))}
                className="rounded"
              />
              <Label htmlFor="is-confirmed">Confirmed</Label>
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowEditDialog(false)}
              className="w-full sm:w-auto order-2 sm:order-1"
            >
              Cancel
            </Button>
            <Button onClick={handleSaveRelationship} className="w-full sm:w-auto order-1 sm:order-2">
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Suggestions Dialog */}
      <Dialog open={showAiSuggestionsDialog} onOpenChange={setShowAiSuggestionsDialog}>
        <DialogContent className="w-[95vw] sm:w-[800px] max-w-[800px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg sm:text-xl">AI Suggested Relationships</DialogTitle>
            <DialogDescription className="text-sm">
              AI has analyzed your schema and suggested the following relationships.
              Review and accept the ones that make sense for your data.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {aiSuggestions.length === 0 ? (
              <p className="text-center text-muted-foreground">No suggestions available.</p>
            ) : (
              <div className="space-y-4">
                {aiSuggestions.map((suggestion, index) => (
                  <Card key={index}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-purple-600" />
                          <Badge variant="secondary">
                            {Math.round(suggestion.confidence_score * 100)}% confidence
                          </Badge>
                          <Badge variant="outline">{suggestion.cardinality}</Badge>
                          <Badge variant="outline">{suggestion.join_type} join</Badge>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 mb-3">
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">Source</div>
                          <div className="font-mono text-sm">
                            {suggestion.source_table}.{suggestion.source_column}
                          </div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">Target</div>
                          <div className="font-mono text-sm">
                            {suggestion.target_table}.{suggestion.target_column}
                          </div>
                        </div>
                      </div>

                      <div className="mb-3">
                        <div className="text-sm font-medium text-muted-foreground">Description</div>
                        <div className="text-sm">{suggestion.description}</div>
                      </div>

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Reasoning</div>
                        <div className="text-sm text-muted-foreground">{suggestion.reasoning}</div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAiSuggestionsDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAcceptAllAiSuggestions}
              disabled={aiSuggesting || aiSuggestions.length === 0}
            >
              {aiSuggesting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Accepting...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Accept All Suggestions
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Relationship details modal */}
      {selectedRelationship && (
        <Dialog open={!!selectedRelationship} onOpenChange={() => setSelectedRelationship(null)}>
          <DialogContent className="w-[90vw] sm:w-[500px] max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="text-lg sm:text-xl">Relationship Details</DialogTitle>
              <DialogDescription className="text-sm">
                Detailed information about this relationship
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Badge variant={
                  selectedRelationship.relationship_type === "db_fk" ? "default" :
                  selectedRelationship.relationship_type === "ai_suggested" ? "secondary" : "outline"
                }>
                  {selectedRelationship.relationship_type === "db_fk" ? "DB FK" :
                   selectedRelationship.relationship_type === "ai_suggested" ? "AI Suggested" : "User Defined"}
                </Badge>
                {selectedRelationship.confidence_score && (
                  <Badge variant="outline">
                    {Math.round(selectedRelationship.confidence_score * 100)}% confidence
                  </Badge>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Source</div>
                  <div className="font-mono text-sm">
                    {selectedRelationship.source_table}.{selectedRelationship.source_column}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Target</div>
                  <div className="font-mono text-sm">
                    {selectedRelationship.target_table}.{selectedRelationship.target_column}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div><span className="text-muted-foreground">Join:</span> {selectedRelationship.join_type}</div>
                <div><span className="text-muted-foreground">Cardinality:</span> {selectedRelationship.cardinality}</div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Agent Approved:</span> {selectedRelationship.agent_approved ? "Yes" : "No"}
                </div>
                <div>
                  <span className="text-muted-foreground">User Accepted:</span> {selectedRelationship.user_accepted ? "Yes" : "No"}
                </div>
              </div>

              <div>
                <div className="text-sm font-medium text-muted-foreground">Description</div>
                <div className="text-sm">{selectedRelationship.description}</div>
              </div>

              <div className="flex gap-2 pt-2">
                <Button size="sm" variant="outline" onClick={() => handleEditRelationship(selectedRelationship)}>
                  <Edit className="h-4 w-4 mr-1" />
                  Edit
                </Button>
                {selectedRelationship.relationship_type !== "db_fk" && (
                  <Button size="sm" variant="outline" onClick={() => handleDeleteRelationship(selectedRelationship.id)}>
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </Button>
                )}
                {selectedRelationship.relationship_type === "ai_suggested" && !selectedRelationship.is_confirmed && (
                  <Button size="sm" onClick={() => handleAcceptAiSuggestion(selectedRelationship)}>
                    <Check className="h-4 w-4 mr-1" />
                    Accept
                  </Button>
                )}
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      <ConfirmationDialog
        open={showDeleteDialog}
        onOpenChange={(open) => {
          setShowDeleteDialog(open)
          if (!open) {
            setRelationshipToDelete(null)
          }
        }}
        title="Delete Relationship"
        description="Are you sure you want to delete this relationship? This action cannot be undone."
        onConfirm={handleDeleteConfirm}
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
      />
    </div>
  )
}


