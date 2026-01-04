"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { PageLoader } from "@/components/ui/loading"
import { EmptyTable } from "@/components/ui/empty-state"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  FileText,
  Download,
  Copy,
  Save,
  Zap,
  Database,
  BookOpen,
  Network,
  Briefcase,
  AlertCircle,
  CheckCircle,
  Loader2,
  Eye,
  Trash2,
  History,
  Settings,
  FileSearch
} from "lucide-react"

interface GeneratedPrompt {
  id: number
  version: number
  prompt_text: string
  schema_snapshot_name: string
  created_at: string
  model_name?: string
  schema_snapshot_id?: number
  tables_count?: number
  columns_count?: number
  relationships_count?: number
}

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  is_active: boolean
  created_at: string
}

interface ActiveConfig {
  schema_snapshot: {
    name: string
    description?: string
  } | null
  model: {
    name: string
  } | null
  data_counts: {
    schema_tables: number
    data_dictionary_entries: number
    relationships: number
    use_cases: number
  }
}

export default function PromptGeneratorPage() {
  const { toast } = useToast()
  const [activeConfig, setActiveConfig] = useState<ActiveConfig | null>(null)
  const [schemaSnapshots, setSchemaSnapshots] = useState<SchemaSnapshot[]>([])
  const [savedPrompts, setSavedPrompts] = useState<GeneratedPrompt[]>([])
  const [generatedPrompt, setGeneratedPrompt] = useState<GeneratedPrompt | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  // Confirmation dialog states
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [promptToDelete, setPromptToDelete] = useState<GeneratedPrompt | null>(null)
  const [activeTab, setActiveTab] = useState("generate")
  const [formData, setFormData] = useState({
    schema_snapshot_id: 0,
    include_data_dictionary: true,
    include_relationships: true,
    include_use_cases: true
  })

  const [selectedSnapshotData, setSelectedSnapshotData] = useState<{
    schema_tables: number
    data_dictionary_entries: number
    relationships: number
    use_cases: number
  } | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      await Promise.all([fetchSchemaSnapshots(), fetchActiveConfig(), fetchSavedPrompts()])
    } catch (error) {
      setError("Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }

  const fetchSavedPrompts = async () => {
    try {
      const response = await fetch("/api/prompt")
      if (response.ok) {
        const prompts = await response.json()
        setSavedPrompts(prompts)
      }
    } catch (error) {
      // Silently handle error
    }
  }

  const fetchSchemaSnapshots = async () => {
    try {
      const response = await fetch("/api/schema/snapshots")
      if (response.ok) {
        const snapshots = await response.json()
        setSchemaSnapshots(snapshots)

        // Set default to active snapshot
        const activeSnapshot = snapshots.find((s: SchemaSnapshot) => s.is_active)
        if (activeSnapshot) {
          setFormData(prev => ({ ...prev, schema_snapshot_id: activeSnapshot.id }))
          // Load data for the active snapshot
          await loadSnapshotData(activeSnapshot.id)
        }
      }
    } catch (error) {
      // Silently handle error
    }
  }

  const loadSnapshotData = async (snapshotId: number) => {
    try {
      const [tablesRes, dictRes, relRes, useCasesRes] = await Promise.all([
        fetch(`/api/schema/tables?snapshot_id=${snapshotId}`),
        fetch(`/api/data-dictionary?snapshot_id=${snapshotId}`),
        fetch(`/api/relationships/${snapshotId}`),
        fetch(`/api/use-cases?snapshot_id=${snapshotId}`)
      ])

      const data = {
        schema_tables: tablesRes.ok ? (await tablesRes.json()).length : 0,
        data_dictionary_entries: dictRes.ok ? (await dictRes.json()).length : 0,
        relationships: relRes.ok ? (await relRes.json()).length : 0,
        use_cases: useCasesRes.ok ? (await useCasesRes.json()).length : 0
      }

      setSelectedSnapshotData(data)
    } catch (error) {
      setSelectedSnapshotData(null)
    }
  }

  const fetchActiveConfig = async () => {
    // No longer needed since we fetch data per snapshot
    // Keeping for potential future use
  }

  const generatePrompt = async () => {
    if (!formData.schema_snapshot_id) {
      setError("Schema snapshot is required")
      return
    }

    setGenerating(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch("/api/prompt-generator/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_snapshot_id: formData.schema_snapshot_id,
          include_data_dictionary: formData.include_data_dictionary,
          include_relationships: formData.include_relationships,
          include_use_cases: formData.include_use_cases
        }),
      })

      if (response.ok) {
        const result = await response.json()
        setGeneratedPrompt(result)
        setSuccess("Prompt generated successfully!")
      } else {
        const errorData = await response.json()
        setError(errorData.detail || "Failed to generate prompt")
      }
    } catch (error) {
      setError("Failed to generate prompt. Please check your connection.")
    } finally {
      setGenerating(false)
    }
  }

  const savePrompt = async () => {
    if (!generatedPrompt) return

    setSaving(true)
    setError(null)

    try {
      // The prompt is already saved when generated, just show success
      setSuccess("Prompt saved successfully!")
    } catch (error) {
      setError("Failed to save prompt")
    } finally {
      setSaving(false)
    }
  }

  const copyToClipboard = async () => {
    if (!generatedPrompt) return

    try {
      await navigator.clipboard.writeText(generatedPrompt.prompt_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      setError("Failed to copy to clipboard")
    }
  }

  const downloadPrompt = () => {
    if (!generatedPrompt) return

    const blob = new Blob([generatedPrompt.prompt_text], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `system-prompt-v${generatedPrompt.version}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleDeletePromptClick = (prompt: GeneratedPrompt) => {
    setPromptToDelete(prompt)
    setShowDeleteDialog(true)
  }

  const handleViewPrompt = (prompt: GeneratedPrompt) => {
    setGeneratedPrompt(prompt)
    setActiveTab("generate")
  }

  const handleDeletePromptConfirm = async () => {
    if (!promptToDelete) return

    try {
      const response = await fetch(`/api/prompt/${promptToDelete.version}`, {
        method: "DELETE",
      })

      if (response.ok) {
        await fetchSavedPrompts()
        toast({
          title: "Success",
          description: "Prompt deleted successfully",
          variant: "success",
        })
      } else {
        const errorData = await response.json()
        toast({
          title: "Error",
          description: errorData.detail || "Failed to delete prompt",
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete prompt. Please try again.",
        variant: "destructive",
      })
    } finally {
      setShowDeleteDialog(false)
      setPromptToDelete(null)
    }
  }

  if (loading) {
    return <PageLoader message="Loading configuration..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Prompt Generator</h1>
          <p className="text-muted-foreground">
            Generate and manage production-ready system prompts for Text-to-SQL agents
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="generate" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Generate Prompt
          </TabsTrigger>
          <TabsTrigger value="manage" className="flex items-center gap-2">
            <FileSearch className="h-4 w-4" />
            Manage Prompts ({savedPrompts.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="generate" className="space-y-6">
          {success && (
            <Alert>
              <CheckCircle className="h-4 w-4" />
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}

          {/* Header Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configuration
          </CardTitle>
          <CardDescription>
            Select schema snapshot and configure prompt generation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Schema Snapshot</Label>
              <Select
                value={formData.schema_snapshot_id.toString()}
                onValueChange={async (value) => {
                  const snapshotId = parseInt(value)
                  setFormData({ ...formData, schema_snapshot_id: snapshotId })
                  await loadSnapshotData(snapshotId)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a schema snapshot" />
                </SelectTrigger>
                <SelectContent>
                  {schemaSnapshots.map((snapshot) => (
                    <SelectItem key={snapshot.id} value={snapshot.id.toString()}>
                      {snapshot.name} {snapshot.is_active && <Badge variant="secondary" className="ml-2">Active</Badge>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

          </div>

          {generatedPrompt && (
            <div className="mt-4 pt-4 border-t">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Latest Generated Prompt</Label>
                  <div className="text-sm text-muted-foreground">
                    Version {generatedPrompt.version} • {generatedPrompt.schema_snapshot_name}
                  </div>
                </div>
                <Badge variant="secondary">v{generatedPrompt.version}</Badge>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Data Overview Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Included Data
          </CardTitle>
          <CardDescription>
            Data that will be included in the generated prompt
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="flex items-center gap-3">
              <Database className="h-8 w-8 text-blue-500" />
              <div>
                <div className="font-medium">Schema Tables</div>
                <div className="text-2xl font-bold">{selectedSnapshotData?.schema_tables || 0}</div>
                <div className="text-sm text-muted-foreground">tables with columns</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-green-500" />
              <div>
                <div className="font-medium">Data Dictionary</div>
                <div className="text-2xl font-bold">{selectedSnapshotData?.data_dictionary_entries || 0}</div>
                <div className="text-sm text-muted-foreground">descriptions & examples</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Network className="h-8 w-8 text-purple-500" />
              <div>
                <div className="font-medium">Relationships</div>
                <div className="text-2xl font-bold">{selectedSnapshotData?.relationships || 0}</div>
                <div className="text-sm text-muted-foreground">explicit joins</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Briefcase className="h-8 w-8 text-orange-500" />
              <div>
                <div className="font-medium">Use Cases</div>
                <div className="text-2xl font-bold">{selectedSnapshotData?.use_cases || 0}</div>
                <div className="text-sm text-muted-foreground">business scenarios</div>
              </div>
            </div>
          </div>

          <Separator className="my-4" />

          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="include_dictionary"
                checked={formData.include_data_dictionary}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, include_data_dictionary: checked as boolean })
                }
              />
              <Label htmlFor="include_dictionary">Include Data Dictionary</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="include_relationships"
                checked={formData.include_relationships}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, include_relationships: checked as boolean })
                }
              />
              <Label htmlFor="include_relationships">Include Relationships</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="include_use_cases"
                checked={formData.include_use_cases}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, include_use_cases: checked as boolean })
                }
              />
              <Label htmlFor="include_use_cases">Include Use Cases</Label>
            </div>

          </div>
        </CardContent>
      </Card>

      {/* Generate Button */}
      <div className="flex justify-center">
        <Button
          onClick={generatePrompt}
          disabled={generating || !formData.schema_snapshot_id}
          size="lg"
          className="px-8"
        >
          {generating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating Prompt...
            </>
          ) : (
            <>
              <Zap className="mr-2 h-4 w-4" />
              Generate System Prompt
            </>
          )}
        </Button>
      </div>

      {/* Generated Prompt Preview */}
      {generatedPrompt && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Generated System Prompt
                </CardTitle>
                <CardDescription>
                  Version {generatedPrompt.version} • Schema: {generatedPrompt.schema_snapshot_name}
                  {generatedPrompt.tables_count !== undefined && ` (${generatedPrompt.tables_count} tables, ${generatedPrompt.columns_count} columns, ${generatedPrompt.relationships_count} relationships)`}
                  {generatedPrompt.model_name && ` • Model: ${generatedPrompt.model_name}`}
                  {' • ' + new Date(generatedPrompt.created_at).toLocaleString()}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyToClipboard}
                  disabled={copied}
                >
                  <Copy className="h-4 w-4 mr-2" />
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadPrompt}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download
                </Button>
                <Button
                  size="sm"
                  onClick={savePrompt}
                  disabled={saving}
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  {saving ? "Saving..." : "Saved"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-muted p-4 rounded-lg">
              <pre className="text-sm whitespace-pre-wrap font-mono">
                {generatedPrompt.prompt_text}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}

          {/* Safety Warning */}
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Read-only SQL Generation:</strong> The generated prompts enforce SELECT-only queries and prevent any data modification operations.
              All prompts include safety constraints to ensure secure database access.
            </AlertDescription>
          </Alert>
        </TabsContent>

        <TabsContent value="manage" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSearch className="h-5 w-5" />
                Saved Prompts
              </CardTitle>
              <CardDescription>
                Manage your generated system prompts and their versions
              </CardDescription>
            </CardHeader>
            <CardContent>
              {savedPrompts.length === 0 ? (
                <EmptyTable
                  icon={FileText}
                  title="No saved prompts"
                  description="Generate your first system prompt to see it here. Prompts are automatically saved when generated."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Version</TableHead>
                      <TableHead>Schema Snapshot</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Content Preview</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {savedPrompts.map((prompt) => (
                      <TableRow key={prompt.id}>
                        <TableCell>
                          <Badge variant="outline">v{prompt.version}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">
                          <div>{prompt.schema_snapshot_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {prompt.tables_count} tables • {prompt.columns_count} columns • {prompt.relationships_count} relationships
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {prompt.model_name || "Unknown"}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          <div>{new Date(prompt.created_at).toLocaleDateString()}</div>
                          <div className="text-xs">{new Date(prompt.created_at).toLocaleTimeString()}</div>
                        </TableCell>
                        <TableCell className="max-w-xs">
                          <div className="text-xs text-muted-foreground truncate">
                            {prompt.prompt_text.substring(0, 100)}...
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleViewPrompt(prompt)}
                              className="flex items-center gap-1"
                            >
                              <Eye className="h-3 w-3" />
                              View
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                const blob = new Blob([prompt.prompt_text], { type: "text/markdown" })
                                const url = URL.createObjectURL(blob)
                                const a = document.createElement("a")
                                a.href = url
                                a.download = `system-prompt-v${prompt.version}.md`
                                document.body.appendChild(a)
                                a.click()
                                document.body.removeChild(a)
                                URL.revokeObjectURL(url)
                              }}
                              className="flex items-center gap-1"
                            >
                              <Download className="h-3 w-3" />
                              Download
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeletePromptClick(prompt)}
                              className="flex items-center gap-1"
                            >
                              <Trash2 className="h-3 w-3" />
                              Delete
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <ConfirmationDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        title="Delete Prompt"
        description={`Are you sure you want to delete prompt version ${promptToDelete?.version}? This action cannot be undone.`}
        onConfirm={handleDeletePromptConfirm}
        confirmText="Delete Prompt"
        cancelText="Cancel"
        variant="destructive"
      />
    </div>
  )
}












