"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Lightbulb, Edit, Trash2, Plus, Search, Filter, Bot, AlertTriangle, Sparkles, Download } from "lucide-react"
import axios from "axios"
import { EmptyState } from "@/components/ui/empty-state"
import { MaturationProcessModal } from "./maturation-process-modal"

interface UseCase {
  id: number
  name: string
  business_goal: string
  example_questions: string[]
  example_queries?: string[]
  output_style: string
  created_at: string
  is_ai_generated: boolean
  generation_log_id?: number
  generation_version?: number
  business_context?: string
  primary_audience?: string[]
  typical_questions_wizard?: string[]
  output_preference?: string
  dictionary_version?: number
  relationships_version?: number
}

interface SchemaSnapshot {
  id: number
  name: string
  description: string
  created_at: string
}

interface UseCasesListProps {
  useCases: UseCase[]
  snapshots: SchemaSnapshot[]
  loading: boolean
  selectedSnapshotId: number | null
  onSnapshotChange: (snapshotId: number | null) => void
  onRefresh: () => void
}

export function UseCasesList({ useCases, snapshots, loading, selectedSnapshotId, onSnapshotChange, onRefresh }: UseCasesListProps) {
  const [searchTerm, setSearchTerm] = useState("")
  const [editingUseCase, setEditingUseCase] = useState<UseCase | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [maturationUseCase, setMaturationUseCase] = useState<UseCase | null>(null)

  const filteredUseCases = useCases.filter(useCase =>
    useCase.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    useCase.business_goal.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleDelete = async (id: number) => {
    try {
      await axios.delete(`/api/use-cases/${id}`)
      onRefresh()
    } catch (error) {
    }
  }

  const handleUpdate = async (useCaseData: Omit<UseCase, 'id' | 'created_at'>) => {
    if (!editingUseCase) return

    try {
      await axios.put(`/api/use-cases/${editingUseCase.id}`, {
        name: useCaseData.name,
        business_goal: useCaseData.business_goal,
        example_questions: useCaseData.example_questions,
        example_queries: useCaseData.example_queries,
        output_style: useCaseData.output_style,
        // Preserve other fields from original use case
        is_ai_generated: editingUseCase.is_ai_generated,
        generation_log_id: editingUseCase.generation_log_id,
        generation_version: editingUseCase.generation_version,
        business_context: editingUseCase.business_context,
        primary_audience: editingUseCase.primary_audience,
        typical_questions_wizard: editingUseCase.typical_questions_wizard,
        output_preference: editingUseCase.output_preference,
        dictionary_version: editingUseCase.dictionary_version,
        relationships_version: editingUseCase.relationships_version
      })
      setEditingUseCase(null)
      onRefresh()
    } catch (error) {
    }
  }

  const handleCreate = async (useCaseData: Omit<UseCase, 'id' | 'created_at'>) => {
    try {
      await axios.post('/api/use-cases', {
        name: useCaseData.name,
        business_goal: useCaseData.business_goal,
        example_questions: useCaseData.example_questions,
        example_queries: useCaseData.example_queries,
        output_style: useCaseData.output_style,
        is_ai_generated: false // Manual creation
      })
      setIsCreateDialogOpen(false)
      onRefresh()
    } catch (error) {
    }
  }

  const handleExportCSV = async () => {
    try {
      let url = '/api/use-cases/export'
      if (selectedSnapshotId) {
        url += `?snapshot_id=${selectedSnapshotId}`
      }
      
      console.log('Exporting CSV from:', url)
      const response = await fetch(url)
      
      console.log('Response status:', response.status, response.statusText)
      console.log('Response headers:', Object.fromEntries(response.headers.entries()))
      
      if (!response.ok) {
        // Try to get error message from response
        let errorMessage = `Failed to export CSV (${response.status})`
        try {
          const errorData = await response.json()
          errorMessage = errorData.error || errorMessage
        } catch {
          try {
            const errorText = await response.text()
            errorMessage = errorText || errorMessage
          } catch {
            // Use default error message
          }
        }
        console.error('Export error:', errorMessage)
        throw new Error(errorMessage)
      }

      // Check if response is actually CSV
      const contentType = response.headers.get("Content-Type")
      console.log('Content-Type:', contentType)
      
      if (contentType && !contentType.includes('csv') && !contentType.includes('text')) {
        // Might be JSON error response
        const errorData = await response.json()
        throw new Error(errorData.error || "Unexpected response format")
      }

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

      // Download file
      const blob = await response.blob()
      const url_obj = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url_obj
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url_obj)
      
      console.log('CSV exported successfully:', filename)
    } catch (error: any) {
      console.error("Failed to export CSV:", error)
      const errorMessage = error?.message || "Failed to export use cases to CSV"
      alert(errorMessage)
    }
  }

  const getOutputStyleBadge = (style: string) => {
    const styles = {
      numeric: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
      summary: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
      analytical: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300"
    }
    return styles[style as keyof typeof styles] || styles.analytical
  }

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with filters, search and create */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search use cases..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 w-64"
            />
          </div>

          <Select
            value={selectedSnapshotId?.toString() || "all"}
            onValueChange={(value) => onSnapshotChange(value === "all" ? null : parseInt(value))}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by snapshot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Snapshots</SelectItem>
              {snapshots.map((snapshot) => (
                <SelectItem key={snapshot.id} value={snapshot.id.toString()}>
                  {snapshot.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleExportCSV} variant="outline" className="gap-2">
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                Add Manually
              </Button>
            </DialogTrigger>
          <DialogContent className="max-w-5xl max-h-[90vh]">
            <DialogHeader>
              <DialogTitle>{isCreateDialogOpen ? 'Add New Use Case' : 'Edit Use Case'}</DialogTitle>
              <DialogDescription>
                {isCreateDialogOpen
                  ? 'Create a new use case manually'
                  : 'Update use case information'
                }
              </DialogDescription>
            </DialogHeader>
            <UseCaseForm
              onSubmit={handleCreate}
              onCancel={() => setIsCreateDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Use Cases Grid */}
      {filteredUseCases.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={Lightbulb}
              title={searchTerm ? 'No use cases found' : 'No use cases available'}
              description={searchTerm
                ? 'Try changing your search term or use the Smart Builder to add new use cases.'
                : 'Use the Smart Use Case Builder to automatically generate practical use cases for your database.'
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredUseCases.map((useCase) => (
            <Card key={useCase.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base line-clamp-2">
                    {useCase.name}
                  </CardTitle>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setMaturationUseCase(useCase)}
                      className="text-blue-600 hover:text-blue-700"
                      title="Start Maturation Process (includes testing existing queries)"
                    >
                      <Sparkles className="h-4 w-4" />
                    </Button>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="sm" onClick={() => setEditingUseCase(useCase)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-5xl max-h-[90vh]">
                        <DialogHeader>
                          <DialogTitle>Edit Use Case</DialogTitle>
                          <DialogDescription>
                            Update the use case information.
                          </DialogDescription>
                        </DialogHeader>
                        {editingUseCase && (
                          <UseCaseForm
                            initialData={editingUseCase}
                            onSubmit={handleUpdate}
                            onCancel={() => setEditingUseCase(null)}
                            isEditing
                          />
                        )}
                      </DialogContent>
                    </Dialog>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Use Case</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete this use case? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(useCase.id)} className="bg-red-600 hover:bg-red-700">
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Badge className={getOutputStyleBadge(useCase.output_style)}>
                    {useCase.output_style === 'numeric' ? 'Numeric' :
                     useCase.output_style === 'summary' ? 'Summary' : 'Analytical'}
                  </Badge>
                  {useCase.is_ai_generated && (
                    <Badge variant="secondary" className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300">
                      <div className="flex items-center gap-1">
                        <Bot className="h-3 w-3" />
                        AI Generated
                      </div>
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm text-muted-foreground mb-3 line-clamp-3">
                  {useCase.business_goal}
                </p>

                {useCase.example_questions && useCase.example_questions.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground">Sample questions:</div>
                    <ul className="text-xs text-muted-foreground space-y-0.5">
                      {useCase.example_questions.slice(0, 2).map((question, index) => (
                        <li key={index} className="line-clamp-1">
                          • {question}
                        </li>
                      ))}
                      {useCase.example_questions.length > 2 && (
                        <li className="text-muted-foreground">
                          and {useCase.example_questions.length - 2} more question{useCase.example_questions.length - 2 !== 1 ? 's' : ''}...
                        </li>
                      )}
                    </ul>
                  </div>
                )}

                <div className="text-xs text-muted-foreground mt-2 space-y-1">
                  <div>Created: {new Date(useCase.created_at).toLocaleDateString('en-US')}</div>
                  {useCase.is_ai_generated && (
                    <div className="flex flex-wrap gap-2 text-xs">
                      {useCase.generation_version && (
                        <span>Version: {useCase.generation_version}</span>
                      )}
                      {useCase.dictionary_version && (
                        <span>Dictionary: v{useCase.dictionary_version}</span>
                      )}
                      {useCase.relationships_version && (
                        <span>Relationships: v{useCase.relationships_version}</span>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Maturation Modal - New Complete Flow */}
      {maturationUseCase && (
        <MaturationProcessModal
          isOpen={!!maturationUseCase}
          onClose={() => setMaturationUseCase(null)}
          useCase={maturationUseCase}
          onComplete={() => {
            setMaturationUseCase(null)
            onRefresh()
          }}
        />
      )}

    </div>
  )
}

// Use Case Form Component
interface UseCaseFormProps {
  initialData?: UseCase
  onSubmit: (data: any) => void
  onCancel: () => void
  isEditing?: boolean
}

function UseCaseForm({ initialData, onSubmit, onCancel, isEditing = false }: UseCaseFormProps) {
  const [formData, setFormData] = useState({
    name: initialData?.name || '',
    business_goal: initialData?.business_goal || '',
    example_questions: initialData?.example_questions || [''],
    example_queries: initialData?.example_queries || [''],
    output_style: initialData?.output_style || 'analytical'
  })

  // Update form data when initialData changes
  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || '',
        business_goal: initialData.business_goal || '',
        example_questions: initialData.example_questions && initialData.example_questions.length > 0
          ? initialData.example_questions
          : [''],
        example_queries: initialData.example_queries && initialData.example_queries.length > 0
          ? initialData.example_queries
          : [''],
        output_style: initialData.output_style || 'analytical'
      })
    }
  }, [initialData])

  // Check if questions and queries counts match
  const questionsCount = formData.example_questions.filter(q => q.trim() !== '').length
  const queriesCount = formData.example_queries.filter(q => q.trim() !== '').length
  const countsMatch = questionsCount === queriesCount

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const cleanedQuestions = formData.example_questions.filter(q => q.trim() !== '')
    const cleanedQueries = formData.example_queries.filter(q => q.trim() !== '')

    // Validate that questions and queries have matching counts
    if (cleanedQuestions.length !== cleanedQueries.length) {
      alert(`Number of questions (${cleanedQuestions.length}) must match number of SQL queries (${cleanedQueries.length})`)
      return
    }

    onSubmit({
      ...formData,
      example_questions: cleanedQuestions.length > 0 ? cleanedQuestions : null,
      example_queries: cleanedQueries.length > 0 ? cleanedQueries : null
    })
  }

  const addQuestion = () => {
    setFormData(prev => ({
      ...prev,
      example_questions: [...prev.example_questions, '']
    }))
  }

  const removeQuestion = (index: number) => {
    setFormData(prev => ({
      ...prev,
      example_questions: prev.example_questions.filter((_, i) => i !== index)
    }))
  }

  const updateQuestion = (index: number, value: string) => {
    setFormData(prev => ({
      ...prev,
      example_questions: prev.example_questions.map((q, i) => i === index ? value : q)
    }))
  }

  const addQuery = () => {
    setFormData(prev => ({
      ...prev,
      example_queries: [...prev.example_queries, '']
    }))
  }

  const removeQuery = (index: number) => {
    setFormData(prev => ({
      ...prev,
      example_queries: prev.example_queries.filter((_, i) => i !== index)
    }))
  }

  const updateQuery = (index: number, value: string) => {
    setFormData(prev => ({
      ...prev,
      example_queries: prev.example_queries.map((q, i) => i === index ? value : q)
    }))
  }

  return (
    <div className="max-h-[80vh] overflow-y-auto">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Validation warning */}
        {!countsMatch && (questionsCount > 0 || queriesCount > 0) && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <AlertTriangle className="h-4 w-4 text-orange-500" />
              </div>
              <div className="mr-3">
                <h3 className="text-sm font-medium text-yellow-800">
                  Questions and queries count must match
                </h3>
                <p className="text-sm text-yellow-700 mt-1">
                  You have {questionsCount} question{questionsCount !== 1 ? 's' : ''} and {queriesCount} quer{queriesCount !== 1 ? 'ies' : 'y'}. Please make them equal.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Basic Information */}
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Use Case Name
            </label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Example: Product price trend analysis"
              className="w-full"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Business Goal
            </label>
            <Textarea
              value={formData.business_goal}
              onChange={(e) => setFormData(prev => ({ ...prev, business_goal: e.target.value }))}
              placeholder="Describe the goal of this use case..."
              rows={3}
              className="w-full resize-none"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Output Style
            </label>
            <select
              value={formData.output_style}
              onChange={(e) => setFormData(prev => ({ ...prev, output_style: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="numeric">Numeric</option>
              <option value="summary">Summary</option>
              <option value="analytical">Analytical</option>
            </select>
          </div>
        </div>

        {/* Questions and Queries Section */}
        <div className="border-t border-gray-200 pt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Sample Questions & SQL Queries
            </h3>
            <div className="flex items-center gap-3">
              <div className="flex gap-4 text-sm">
                <span className="text-gray-600">
                  Questions: <span className="font-medium text-blue-600">{questionsCount}</span>
                </span>
                <span className="text-gray-600">
                  Queries: <span className="font-medium text-green-600">{queriesCount}</span>
                </span>
              </div>
              <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                countsMatch
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                {countsMatch ? (
                  <>
                    <span>✓</span>
                    <span>Matched</span>
                  </>
                ) : (
                  <>
                    <span>✗</span>
                    <span>Mismatched</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Sample Questions */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">
                  Sample Questions ({questionsCount})
                </label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addQuestion}
                  className="text-xs"
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add Question
                </Button>
              </div>

              <div className="space-y-3 max-h-60 overflow-y-auto border border-gray-200 rounded-md p-3">
                {formData.example_questions.map((question, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <span className="text-xs text-gray-500 mt-2 min-w-[20px]">
                      {index + 1}.
                    </span>
                    <Input
                      value={question}
                      onChange={(e) => updateQuestion(index, e.target.value)}
                      placeholder={index === 0 ? "Which products have the highest sales?" : `Sample question ${index + 1}`}
                      className="flex-1 text-sm"
                    />
                    {formData.example_questions.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeQuestion(index)}
                        className="text-red-600 hover:text-red-700 mt-0"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* SQL Queries */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">
                  SQL Queries ({queriesCount})
                </label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addQuery}
                  className="text-xs"
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add Query
                </Button>
              </div>

              <div className="space-y-3 max-h-60 overflow-y-auto border border-gray-200 rounded-md p-3">
                {formData.example_queries.map((query, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <span className="text-xs text-gray-500 mt-2 min-w-[20px]">
                      {index + 1}.
                    </span>
                    <Textarea
                      value={query}
                      onChange={(e) => updateQuery(index, e.target.value)}
                      placeholder={index === 0 ? "SELECT product_name, SUM(sales) as total_sales FROM products GROUP BY product_name ORDER BY total_sales DESC LIMIT 10;" : `SQL query ${index + 1}`}
                      className="flex-1 text-sm font-mono text-xs resize-none"
                      rows={3}
                    />
                    {formData.example_queries.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeQuery(index)}
                        className="text-red-600 hover:text-red-700 mt-0"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Form Actions */}
        <div className="border-t pt-6 flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            className="px-6"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!countsMatch && (questionsCount > 0 || queriesCount > 0)}
            className="px-6"
          >
            {isEditing ? 'Update' : 'Add'}
          </Button>
        </div>
      </form>
    </div>
  )
}