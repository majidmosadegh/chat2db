"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Check,
  X,
  Edit,
  Trash2,
  Database,
  Table,
  Key,
  AlertCircle,
  Plus
} from "lucide-react"
import { RelationshipCanvas } from "@/components/relationships/relationship-canvas"
import { PageLoader } from "@/components/ui/loading"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

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

interface RelationshipEdge {
  id: string
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship: Relationship
}

export default function RelationshipsPage() {
  const { toast } = useToast()
  const params = useParams()
  const snapshotId = params.snapshot_id as string

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
  const [showAiResultsDialog, setShowAiResultsDialog] = useState(false)
  const [aiSuggestions, setAiSuggestions] = useState<any[]>([])
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<number>>(new Set())

  // Filtering states - using simplified category names
  const [cleanMode, setCleanMode] = useState(false) // Clean mode: only highest-ranked per table pair
  const [showDatabaseRelations, setShowDatabaseRelations] = useState(true) // schema_fk
  const [showAiRelations, setShowAiRelations] = useState(false) // ai_suggested
  const [showUserRelations, setShowUserRelations] = useState(true) // manual
  const [advancedMode, setAdvancedMode] = useState(false)
  const [selectedRelationship, setSelectedRelationship] = useState<Relationship | null>(null)
  
  // Delete confirmation dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [relationshipToDelete, setRelationshipToDelete] = useState<number | null>(null)

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
    if (snapshotId) {
      loadData()
    }
  }, [snapshotId, cleanMode, showDatabaseRelations, showAiRelations, showUserRelations])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Build filter parameters using simplified category names
      const includeTypes = []
      if (showDatabaseRelations) includeTypes.push("database")
      if (showAiRelations) includeTypes.push("ai_suggested")
      if (showUserRelations) includeTypes.push("user_added")

      const filterParams = new URLSearchParams({
        include_types: includeTypes.join(",") || "all",
        clean_mode: cleanMode.toString()
      })

      // Load relationships and schema data in parallel
      const [relationshipsRes, schemaRes] = await Promise.all([
        fetch(`/api/relationships/${snapshotId}?${filterParams}`),
        fetch(`/api/schema/tables?snapshot_id=${snapshotId}`)
      ])

      if (relationshipsRes.ok) {
        const relationshipsData = await relationshipsRes.json()
        setRelationships(relationshipsData)
      }

      if (schemaRes.ok) {
        const schemaData = await schemaRes.json()
        // Convert schema data to table nodes with positions
        const nodes: TableNode[] = schemaData.map((table: any, index: number) => ({
          id: `${table.schema_name}.${table.table_name}`,
          schema_name: table.schema_name,
          table_name: table.table_name,
          row_count: table.row_count || 0,
          columns: table.columns || [],
          x: 100 + (index % 4) * 300, // Simple grid layout
          y: 100 + Math.floor(index / 4) * 250
        }))
        setTableNodes(nodes)
      }

    } catch (err) {
      setError("Failed to load data")
    } finally {
      setLoading(false)
    }
  }

  const handleAiSuggest = async () => {
    try {
      setAiSuggesting(true)
      setError(null)

      const response = await fetch("/api/relationships/ai-suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_snapshot_id: parseInt(snapshotId),
          business_context: aiBusinessContext.trim() || undefined
        })
      })

      if (response.ok) {
        const data = await response.json()
        // Show suggestions in dialog for user review
        setAiSuggestions(data.suggested_relationships || [])
        setSelectedSuggestions(new Set()) // Reset selections
        setShowAiSuggestDialog(false)
        setShowAiResultsDialog(true)
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
    setEditingRelationship(relationship)
    setEditForm({
      source_table: relationship.source_table,
      source_column: relationship.source_column,
      target_table: relationship.target_table,
      target_column: relationship.target_column,
      relationship_type: relationship.relationship_type,
      join_type: relationship.join_type,
      cardinality: relationship.cardinality,
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

  const handlePromoteForAgent = async (relationship: Relationship) => {
    try {
      const response = await fetch(`/api/relationships/${relationship.id}/promote`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      })

      if (response.ok) {
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to promote relationship")
      }
    } catch (err) {
      setError("Failed to promote relationship")
    }
  }

  const handleAcceptAiSuggestions = async () => {
    const suggestionsToAccept = aiSuggestions.filter((_, index) => selectedSuggestions.has(index))

    if (suggestionsToAccept.length === 0) {
      toast({
        title: "Warning",
        description: "Please select at least one suggestion to accept.",
        variant: "warning",
      })
      return
    }

    try {
      const response = await fetch("/api/relationships/ai-suggest/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          suggestions: suggestionsToAccept,
          snapshot_id: parseInt(snapshotId)
        })
      })

      if (response.ok) {
        const result = await response.json()
        toast({
          title: "Success",
          description: `Successfully created ${result.created_relationships?.length || 0} relationships!`,
          variant: "success",
        })
        setShowAiResultsDialog(false)
        setAiSuggestions([])
        setSelectedSuggestions(new Set())
        await loadData()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to accept AI suggestions")
      }
    } catch (err) {
      setError("Failed to accept AI suggestions")
    }
  }

  const toggleSuggestionSelection = (index: number) => {
    const newSelected = new Set(selectedSuggestions)
    if (newSelected.has(index)) {
      newSelected.delete(index)
    } else {
      newSelected.add(index)
    }
    setSelectedSuggestions(newSelected)
  }

  const handleExportForAgent = async () => {
    try {
      const response = await fetch(`/api/relationships/agent-export/${snapshotId}`)
      if (response.ok) {
        const data = await response.json()
        // Copy to clipboard or download as JSON
        const jsonString = JSON.stringify(data, null, 2)
        navigator.clipboard.writeText(jsonString)
        toast({
          title: "Success",
          description: "Agent export data copied to clipboard!",
          variant: "success",
        })
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to export for agent")
      }
    } catch (err) {
      setError("Failed to export for agent")
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

  const handleFormCreateRelationship = async () => {
    // Validate required fields
    if (!createForm.source_table || !createForm.source_column ||
        !createForm.target_table || !createForm.target_column ||
        !createForm.description.trim()) {
      setError("Please fill in all required fields")
      return
    }

    try {
      const response = await fetch("/api/relationships", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_snapshot_id: parseInt(snapshotId),
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

  const getRelationshipColor = (type: string) => {
    switch (type) {
      case "db_fk": return "text-gray-600"
      case "ai_suggested": return "text-blue-600"
      case "user_defined": return "text-green-600"
      default: return "text-gray-600"
    }
  }

  const getRelationshipStyle = (type: string) => {
    switch (type) {
      case "db_fk": return "solid"
      case "ai_suggested": return "dashed"
      case "user_defined": return "solid"
      default: return "solid"
    }
  }

  if (loading) {
    return <PageLoader message="Loading relationships..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Schema Relationships</h1>
          <p className="text-muted-foreground">
            Manage relationships for schema snapshot #{snapshotId}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setShowCreateDialog(true)}
            variant="outline"
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Create Relationship
          </Button>
          <Button
            onClick={() => setShowAiSuggestDialog(true)}
            disabled={aiSuggesting}
            className="flex items-center gap-2"
          >
            {aiSuggesting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {aiSuggesting ? "Suggesting..." : "Suggest Relationships"}
          </Button>
          <Button
            onClick={handleExportForAgent}
            variant="outline"
            className="flex items-center gap-2"
          >
            <ArrowRight className="h-4 w-4" />
            Export for Agent
          </Button>
        </div>

        {/* Relationship Type Filters */}
        <div className="flex items-center gap-4 border rounded-lg p-3 bg-muted/30">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="database-relations"
              checked={showDatabaseRelations}
              onChange={(e) => setShowDatabaseRelations(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="database-relations" className="text-sm">دیتابیس داشته</Label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="user-relations"
              checked={showUserRelations}
              onChange={(e) => setShowUserRelations(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="user-relations" className="text-sm">کاربر اضافه کرده</Label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="ai-relations"
              checked={showAiRelations}
              onChange={(e) => setShowAiRelations(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="ai-relations" className="text-sm">پیشنهاد AI بوده</Label>
          </div>
          <Separator orientation="vertical" className="h-6" />
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="clean-mode"
              checked={cleanMode}
              onChange={(e) => setCleanMode(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="clean-mode" className="text-sm">Clean Mode</Label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="advanced-mode"
              checked={advancedMode}
              onChange={(e) => setAdvancedMode(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="advanced-mode" className="text-sm">Advanced Mode</Label>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {/* Visual Canvas */}
      <Card>
        <CardHeader>
          <CardTitle>Relationship Diagram</CardTitle>
          <CardDescription>
            Visual representation of tables and their relationships. Drag from one column to another to create relationships.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tableNodes.length === 0 ? (
            <div className="h-96 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No tables loaded.</p>
                <p className="text-sm">Make sure schema introspection has been run.</p>
              </div>
            </div>
          ) : (
            <div>
              <RelationshipCanvas
                tableNodes={tableNodes}
                relationships={relationships}
                onEditRelationship={handleEditRelationship}
                onDeleteRelationship={handleDeleteRelationship}
                onAcceptRelationship={handleAcceptAiSuggestion}
                onCreateRelationship={handleDragCreateRelationship}
                onOpenCreateRelationshipModal={handleOpenCreateRelationshipModal}
                cleanMode={cleanMode}
                advancedMode={advancedMode}
                onRelationshipClick={(relationship) => setSelectedRelationship(relationship)}
              />

            {/* Debug info */}
            <div style={{
              position: 'fixed',
              bottom: '10px',
              right: '10px',
              background: 'white',
              padding: '10px',
              border: '1px solid black',
              zIndex: 9999,
              maxWidth: '400px',
              fontSize: '12px'
            }}>
              <div><strong>Debug Info:</strong></div>
              <div>Relationships: {relationships.length}</div>
              <div>Table Nodes: {tableNodes.length}</div>
              <div>Table Node IDs: {tableNodes.map(n => n.id).join(', ')}</div>
              <div>Relationship sources: {relationships.map(r => r.source_table).join(', ')}</div>
              <div>Relationship targets: {relationships.map(r => r.target_table).join(', ')}</div>
            </div>
              {relationships.length === 0 && (
                <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-800 dark:text-blue-200">
                    <Plus className="h-5 w-5" />
                    <span className="font-medium">Getting Started</span>
                  </div>
                  <p className="mt-2 text-sm text-blue-700 dark:text-blue-300">
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
      <Card>
        <CardHeader>
          <CardTitle>Relationships ({relationships.length})</CardTitle>
          <CardDescription>
            All relationships in this schema snapshot
          </CardDescription>
        </CardHeader>
        <CardContent>
          {relationships.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Table className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No relationships found.</p>
              <p className="text-sm mb-4">Use the buttons above to create relationships manually or get AI suggestions.</p>
              <div className="flex justify-center gap-2">
                <Button
                  onClick={() => setShowCreateDialog(true)}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Create Relationship
                </Button>
                <Button
                  onClick={() => setShowAiSuggestDialog(true)}
                  className="flex items-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  Suggest Relationships
                </Button>
              </div>
            </div>
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
                      {!rel.agent_approved && rel.strength_score && rel.strength_score > 0.6 && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handlePromoteForAgent(rel)}
                          className="flex items-center gap-1"
                        >
                          <ArrowRight className="h-4 w-4" />
                          Promote
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">Source</div>
                      <div className="font-mono text-sm">
                        {rel.source_table}.{rel.source_column}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">Target</div>
                      <div className="font-mono text-sm">
                        {rel.target_table}.{rel.target_column}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Join:</span> {rel.join_type}
                    </div>
                    <div>
                      <span className="text-muted-foreground">Cardinality:</span> {rel.cardinality}
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

      {/* Create Relationship Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Create New Relationship</DialogTitle>
            <DialogDescription>
              Manually create a relationship between two tables in your schema.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-source-table" className="text-right">
                  Source Table *
                </Label>
                <Select
                  value={createForm.source_table}
                  onValueChange={(value) => setCreateForm(prev => ({
                    ...prev,
                    source_table: value,
                    source_column: "" // Reset column when table changes
                  }))}
                >
                  <SelectTrigger className="col-span-3">
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
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-target-table" className="text-right">
                  Target Table *
                </Label>
                <Select
                  value={createForm.target_table}
                  onValueChange={(value) => setCreateForm(prev => ({
                    ...prev,
                    target_table: value,
                    target_column: "" // Reset column when table changes
                  }))}
                >
                  <SelectTrigger className="col-span-3">
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
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-source-column" className="text-right">
                  Source Column *
                </Label>
                <Select
                  value={createForm.source_column}
                  onValueChange={(value) => setCreateForm(prev => ({ ...prev, source_column: value }))}
                  disabled={!createForm.source_table}
                >
                  <SelectTrigger className="col-span-3">
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
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-target-column" className="text-right">
                  Target Column *
                </Label>
                <Select
                  value={createForm.target_column}
                  onValueChange={(value) => setCreateForm(prev => ({ ...prev, target_column: value }))}
                  disabled={!createForm.target_table}
                >
                  <SelectTrigger className="col-span-3">
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

            <div className="grid grid-cols-3 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-join-type" className="text-right">
                  Join Type
                </Label>
                <Select
                  value={createForm.join_type}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, join_type: value }))}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inner">Inner</SelectItem>
                    <SelectItem value="left">Left</SelectItem>
                    <SelectItem value="right">Right</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-cardinality" className="text-right">
                  Cardinality
                </Label>
                <Select
                  value={createForm.cardinality}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, cardinality: value }))}
                >
                  <SelectTrigger className="col-span-3">
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

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="create-relationship-type" className="text-right">
                  Type
                </Label>
                <Select
                  value={createForm.relationship_type}
                  onValueChange={(value: any) => setCreateForm(prev => ({ ...prev, relationship_type: value }))}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user_defined">User Defined</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-4 items-start gap-4">
              <Label htmlFor="create-description" className="text-right pt-2">
                Description *
              </Label>
              <Textarea
                id="create-description"
                value={createForm.description}
                onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Describe this relationship..."
                className="col-span-3"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleFormCreateRelationship}>
              Create Relationship
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Suggest Dialog */}
      <Dialog open={showAiSuggestDialog} onOpenChange={setShowAiSuggestDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Get AI Relationship Suggestions</DialogTitle>
            <DialogDescription>
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

      {/* AI Results Dialog */}
      <Dialog open={showAiResultsDialog} onOpenChange={setShowAiResultsDialog}>
        <DialogContent className="sm:max-w-[800px]">
          <DialogHeader>
            <DialogTitle>AI Relationship Suggestions</DialogTitle>
            <DialogDescription>
              Review and select the relationships you want to add to your schema.
              AI has suggested {aiSuggestions.length} relationships based on your schema analysis.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {aiSuggestions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No suggestions found.</p>
                <p className="text-sm">Try providing more business context.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {aiSuggestions.map((suggestion, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selectedSuggestions.has(index)}
                        onChange={() => toggleSuggestionSelection(index)}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline">
                            {suggestion.join_type} - {suggestion.cardinality}
                          </Badge>
                          <Badge variant="secondary">
                            {(suggestion.confidence_score * 100).toFixed(1)}% confidence
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm mb-2">
                          <div>
                            <span className="font-medium">From:</span> {suggestion.source_table}.{suggestion.source_column}
                          </div>
                          <div>
                            <span className="font-medium">To:</span> {suggestion.target_table}.{suggestion.target_column}
                          </div>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {suggestion.description}
                        </div>
                        {suggestion.reasoning && (
                          <div className="text-xs text-muted-foreground mt-2 p-2 bg-muted rounded">
                            <strong>AI Reasoning:</strong> {suggestion.reasoning}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter className="gap-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              Selected: {selectedSuggestions.size} of {aiSuggestions.length}
            </div>
            <Button
              variant="outline"
              onClick={() => setShowAiResultsDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAcceptAiSuggestions}
              disabled={selectedSuggestions.size === 0}
            >
              Accept Selected ({selectedSuggestions.size})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Relationship Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Relationship</DialogTitle>
            <DialogDescription>
              Modify the relationship properties.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="source-table" className="text-right">
                  Source Table
                </Label>
                <Input
                  id="source-table"
                  value={editForm.source_table}
                  onChange={(e) => setEditForm(prev => ({ ...prev, source_table: e.target.value }))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="target-table" className="text-right">
                  Target Table
                </Label>
                <Input
                  id="target-table"
                  value={editForm.target_table}
                  onChange={(e) => setEditForm(prev => ({ ...prev, target_table: e.target.value }))}
                  className="col-span-3"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="source-column" className="text-right">
                  Source Column
                </Label>
                <Input
                  id="source-column"
                  value={editForm.source_column}
                  onChange={(e) => setEditForm(prev => ({ ...prev, source_column: e.target.value }))}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="target-column" className="text-right">
                  Target Column
                </Label>
                <Input
                  id="target-column"
                  value={editForm.target_column}
                  onChange={(e) => setEditForm(prev => ({ ...prev, target_column: e.target.value }))}
                  className="col-span-3"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="join-type" className="text-right">
                  Join Type
                </Label>
                <Select
                  value={editForm.join_type}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, join_type: value }))}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inner">Inner</SelectItem>
                    <SelectItem value="left">Left</SelectItem>
                    <SelectItem value="right">Right</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="cardinality" className="text-right">
                  Cardinality
                </Label>
                <Select
                  value={editForm.cardinality}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, cardinality: value }))}
                >
                  <SelectTrigger className="col-span-3">
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

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="relationship-type" className="text-right">
                  Type
                </Label>
                <Select
                  value={editForm.relationship_type}
                  onValueChange={(value: any) => setEditForm(prev => ({ ...prev, relationship_type: value }))}
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user_defined">User Defined</SelectItem>
                    <SelectItem value="ai_suggested">AI Suggested</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-4 items-start gap-4">
              <Label htmlFor="description" className="text-right pt-2">
                Description
              </Label>
              <Textarea
                id="description"
                value={editForm.description}
                onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                className="col-span-3"
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
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEditDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveRelationship}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Relationship details modal */}
      {selectedRelationship && (
        <Dialog open={!!selectedRelationship} onOpenChange={() => setSelectedRelationship(null)}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Relationship Details</DialogTitle>
              <DialogDescription>
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















