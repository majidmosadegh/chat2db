"use client"

import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"
import { Sparkles, CheckCircle2, XCircle, Loader2, Play, Pause, RefreshCw, Eye, EyeOff, Trash2, TestTube, AlertCircle } from "lucide-react"
import axios from "axios"

interface UseCase {
  id: number
  name: string
}

interface MaturationSession {
  id: number
  use_case_id: number
  status: string
  current_step: string | null
  language: string
  total_questions_generated: number
  total_questions_processed: number
  successful_questions: number
  failed_questions: number
  stored_questions: number
  success_rate: number | null
}

interface MaturationQuestion {
  id: number
  question_index: number
  question_text: string
  generated_sql: string | null
  execution_status: string | null
  execution_result: any
  execution_error: string | null
  retry_count: number
  user_approval: string | null
  user_feedback: string | null
  is_stored: boolean
}

interface MaturationProcessModalProps {
  isOpen: boolean
  onClose: () => void
  useCase: UseCase | null
  onComplete: () => void
}

export function MaturationProcessModal({
  isOpen,
  onClose,
  useCase,
  onComplete
}: MaturationProcessModalProps) {
  const [session, setSession] = useState<MaturationSession | null>(null)
  const [questions, setQuestions] = useState<MaturationQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedQuestion, setExpandedQuestion] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<{ [key: number]: string }>({})
  const [processingQuestion, setProcessingQuestion] = useState<number | null>(null)
  const [existingTestResults, setExistingTestResults] = useState<any>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [selectedFailedIndices, setSelectedFailedIndices] = useState<Set<number>>(new Set())
  const [activeTab, setActiveTab] = useState<"new" | "existing">("new")
  const [improving, setImproving] = useState(false)
  const [improvementStatus, setImprovementStatus] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && useCase && !session) {
      createSession()
    }
    
    // Reset state when modal closes
    if (!isOpen) {
      setSession(null)
      setQuestions([])
      setExpandedQuestion(null)
      setFeedback({})
      setExistingTestResults(null)
      setAnalysis(null)
      setSelectedFailedIndices(new Set())
      setActiveTab("new")
    }
  }, [isOpen, useCase])

  useEffect(() => {
    if (!isOpen) return // Don't poll if modal is closed
    
    if (session && session.id && session.status !== "completed" && session.status !== "failed") {
      const interval = setInterval(() => {
        fetchStatus()
      }, 2000) // Poll every 2 seconds
      return () => clearInterval(interval)
    }
  }, [isOpen, session?.id, session?.status])

  const createSession = async () => {
    if (!useCase || session) return // Don't create if already exists

    setLoading(true)
    try {
      const response = await axios.post("/api/maturation/sessions", {
        use_case_id: useCase.id,
        language: "persian",
        questions_per_batch: 5,
        max_retries_per_question: 3
      })
      setSession(response.data)
      setError(null)
      // Auto-start after a brief delay
      setTimeout(() => {
        startSession(response.data.id)
      }, 500)
    } catch (error: any) {
      console.error("Failed to create session:", error)
      let errorMsg = "Unknown error"
      
      if (error.response) {
        // Server responded with error
        errorMsg = error.response.data?.detail || error.response.data?.error || error.response.statusText
      } else if (error.request) {
        // Request made but no response (network error)
        errorMsg = "Network error: Could not connect to backend. Please make sure the backend server is running."
      } else {
        // Something else happened
        errorMsg = error.message || "Unknown error"
      }
      
      setError(errorMsg)
      alert(`Failed to create maturation session: ${errorMsg}`)
    } finally {
      setLoading(false)
    }
  }

  const startSession = async (sessionId: number) => {
    try {
      console.log(`[MATURATION] Starting session ${sessionId}`)
      const response = await axios.post(`/api/maturation/sessions/${sessionId}/start`)
      console.log(`[MATURATION] Start response:`, response.data)
      fetchStatus()
    } catch (error: any) {
      console.error("Failed to start session:", error)
      setError(error.response?.data?.detail || error.message || "Failed to start session")
    }
  }

  const fetchStatus = async () => {
    if (!session?.id) return

    try {
      const response = await axios.get(`/api/maturation/sessions/${session.id}/status`)
      setSession(response.data.session)
      setQuestions(response.data.questions || [])
      setExistingTestResults(response.data.existing_test_results || null)
      setAnalysis(response.data.analysis || null)
      setError(null) // Clear any previous errors
    } catch (error: any) {
      console.error("Failed to fetch status:", error)
      // If session not found, stop polling
      if (error.response?.status === 404) {
        setSession(null)
        setError("Session not found")
      } else if (error.request && !error.response) {
        // Network error - don't show alert for polling errors
        console.warn("Network error during status fetch (polling)")
      }
    }
  }

  const handleApprove = async (questionId: number, approval: "approved" | "rejected") => {
    if (processingQuestion === questionId) return // Prevent double-click
    
    setProcessingQuestion(questionId)
    try {
      await axios.post(`/api/maturation/questions/${questionId}/approve`, {
        approval,
        feedback: feedback[questionId] || null
      })
      // Update local state immediately
      setQuestions(prev => prev.map(q => 
        q.id === questionId 
          ? { ...q, user_approval: approval, user_feedback: feedback[questionId] || null, is_stored: approval === "approved" }
          : q
      ))
      // Update session stored count
      if (approval === "approved" && session) {
        setSession(prev => prev ? { ...prev, stored_questions: (prev.stored_questions || 0) + 1 } : null)
      }
      // Refresh from server
      await fetchStatus()
      // Clear feedback
      setFeedback(prev => {
        const newFeedback = { ...prev }
        delete newFeedback[questionId]
        return newFeedback
      })
    } catch (error: any) {
      console.error("Failed to approve question:", error)
      alert(`Failed to ${approval} question: ${error.response?.data?.detail || error.message}`)
    } finally {
      setProcessingQuestion(null)
    }
  }

  const handlePause = async () => {
    if (!session) return
    try {
      await axios.post(`/api/maturation/sessions/${session.id}/pause`)
      fetchStatus()
    } catch (error: any) {
      console.error("Failed to pause:", error)
    }
  }

  const handleResume = async () => {
    if (!session) return
    try {
      await axios.post(`/api/maturation/sessions/${session.id}/resume`)
      fetchStatus()
    } catch (error: any) {
      console.error("Failed to resume:", error)
    }
  }

  const handleRemoveFailedQueries = async () => {
    if (!useCase || selectedFailedIndices.size === 0) return

    setLoading(true)
    try {
      await axios.post(`/api/maturation/use-cases/${useCase.id}/remove-queries`, {
        indices: Array.from(selectedFailedIndices)
      })
      setSelectedFailedIndices(new Set())
      await fetchStatus()
      onComplete()
    } catch (error: any) {
      console.error("Failed to remove queries:", error)
      alert(`Failed to remove queries: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  if (!useCase) return null

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "text-green-600"
      case "processing": return "text-blue-600"
      case "failed": return "text-red-600"
      case "paused": return "text-yellow-600"
      default: return "text-gray-600"
    }
  }

  const getStatusBadge = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status) {
      case "completed": return "default"
      case "processing": return "default"
      case "failed": return "destructive"
      case "paused": return "secondary"
      default: return "secondary"
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Use Case Maturation Process
          </DialogTitle>
          <DialogDescription>
            Continuous maturation: Generate questions, execute SQL, and store successful pairs
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-800">{error}</p>
            <Button 
              onClick={() => {
                setError(null)
                if (useCase) createSession()
              }} 
              variant="outline" 
              size="sm" 
              className="mt-2"
            >
              Retry
            </Button>
          </div>
        )}

        {loading && !session ? (
          <div className="flex flex-col items-center justify-center py-12 space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-muted-foreground">Creating maturation session...</p>
          </div>
        ) : session ? (
          <div className="space-y-6">
            {/* Session Status */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm font-medium">Status</p>
                  <Badge variant={getStatusBadge(session.status)} className="mt-1">
                    {session.status}
                  </Badge>
                </div>
                <div className="flex gap-2">
                  {session.status === "processing" && (
                    <Button onClick={handlePause} variant="outline" size="sm">
                      <Pause className="h-4 w-4 mr-2" />
                      Pause
                    </Button>
                  )}
                  {session.status === "paused" && (
                    <Button onClick={handleResume} variant="outline" size="sm">
                      <Play className="h-4 w-4 mr-2" />
                      Resume
                    </Button>
                  )}
                  <Button onClick={fetchStatus} variant="outline" size="sm">
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* Current Step Display */}
              {session.current_step && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Current Step:</p>
                  <div className="flex items-center gap-2">
                    {session.current_step === "testing_existing_queries" && (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        <span className="text-sm">Testing existing queries...</span>
                      </>
                    )}
                    {session.current_step === "loading_context" && (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        <span className="text-sm">Loading database context...</span>
                      </>
                    )}
                    {session.current_step === "generating_questions" && (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        <span className="text-sm">Generating questions...</span>
                      </>
                    )}
                    {session.current_step?.startsWith("processing_question_") && (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        <span className="text-sm">{session.current_step.replace(/_/g, " ").replace("processing question", "Processing question")}</span>
                      </>
                    )}
                    {session.current_step === "analyzing_results" && (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        <span className="text-sm">Analyzing results...</span>
                      </>
                    )}
                    {!["testing_existing_queries", "loading_context", "generating_questions", "analyzing_results"].includes(session.current_step) && 
                     !session.current_step?.startsWith("processing_question_") && (
                      <span className="text-sm">{session.current_step}</span>
                    )}
                  </div>
                </div>
              )}

              {/* Statistics */}
              <div className="grid grid-cols-4 gap-4 mt-4">
                <div>
                  <p className="text-xs text-muted-foreground">Generated</p>
                  <p className="text-lg font-semibold">{session.total_questions_generated}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Processed</p>
                  <p className="text-lg font-semibold">{session.total_questions_processed}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Success</p>
                  <p className="text-lg font-semibold text-green-600">{session.successful_questions}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Stored</p>
                  <p className="text-lg font-semibold text-blue-600">{session.stored_questions}</p>
                </div>
              </div>

              {session.success_rate !== null && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-muted-foreground">Success Rate</span>
                    <span className="text-xs font-medium">{(session.success_rate * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={session.success_rate * 100} />
                </div>
              )}
            </div>

            {/* Tabs for New Questions and Existing Queries */}
            {(existingTestResults || analysis) && (
              <div className="border-b">
                <div className="flex gap-2">
                  <Button
                    variant={activeTab === "new" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("new")}
                  >
                    New Questions ({questions.length})
                  </Button>
                  <Button
                    variant={activeTab === "existing" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setActiveTab("existing")}
                  >
                    Existing Queries ({existingTestResults?.total_queries || 0})
                  </Button>
                </div>
              </div>
            )}

            {/* Existing Queries Test Results */}
            {activeTab === "existing" && existingTestResults && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="grid grid-cols-4 gap-4 mb-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Total</p>
                      <p className="text-lg font-semibold">{existingTestResults.total_queries}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Tested</p>
                      <p className="text-lg font-semibold">{existingTestResults.tested_queries}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Successful</p>
                      <p className="text-lg font-semibold text-green-600">{existingTestResults.successful_queries}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Failed</p>
                      <p className="text-lg font-semibold text-red-600">{existingTestResults.failed_queries}</p>
                    </div>
                  </div>
                  {existingTestResults.tested_queries > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Success Rate</span>
                        <span className="text-xs font-medium">
                          {(existingTestResults.success_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={existingTestResults.success_rate * 100} />
                    </div>
                  )}
                </div>

                {/* Recommendations */}
                {analysis && analysis.recommendations && analysis.recommendations.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">Recommendations</h4>
                    {analysis.recommendations.map((rec: any, idx: number) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-lg border ${
                          rec.priority === "high"
                            ? "bg-red-50 border-red-200"
                            : "bg-yellow-50 border-yellow-200"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <AlertCircle className={`h-4 w-4 mt-0.5 ${
                            rec.priority === "high" ? "text-red-600" : "text-yellow-600"
                          }`} />
                          <div className="flex-1">
                            <p className="text-sm font-medium">{rec.message}</p>
                            {rec.suggestion && (
                              <p className="text-xs text-muted-foreground mt-1">{rec.suggestion}</p>
                            )}
                            {rec.failed_indices && rec.failed_indices.length > 0 && (
                              <Button
                                onClick={() => setSelectedFailedIndices(new Set(rec.failed_indices))}
                                variant="outline"
                                size="sm"
                                className="mt-2"
                              >
                                Select Failed Queries
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Failed Queries Actions */}
                {existingTestResults.failed_queries > 0 && (
                  <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
                    <div>
                      <p className="text-sm font-medium">
                        {selectedFailedIndices.size} query(ies) selected for removal
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Failed queries can be removed to improve use case quality
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => {
                          const failedIndices = existingTestResults.results
                            .filter((r: any) => r.status !== "success")
                            .map((r: any) => r.index)
                          setSelectedFailedIndices(new Set(failedIndices))
                        }}
                        variant="outline"
                        size="sm"
                      >
                        Select All Failed
                      </Button>
                      <Button
                        onClick={handleRemoveFailedQueries}
                        disabled={loading || selectedFailedIndices.size === 0}
                        variant="destructive"
                        size="sm"
                      >
                        {loading ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4 mr-2" />
                        )}
                        Remove Selected
                      </Button>
                    </div>
                  </div>
                )}

                {/* Query Results List */}
                <div className="space-y-3">
                  <h4 className="font-medium text-sm">Query Test Results</h4>
                  {existingTestResults.results.map((result: any) => (
                    <div
                      key={result.index}
                      className={`border rounded-lg p-4 space-y-3 ${
                        selectedFailedIndices.has(result.index) ? "bg-blue-50 border-blue-300" : ""
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {result.status !== "success" && (
                              <input
                                type="checkbox"
                                checked={selectedFailedIndices.has(result.index)}
                                onChange={() => {
                                  const newSelected = new Set(selectedFailedIndices)
                                  if (newSelected.has(result.index)) {
                                    newSelected.delete(result.index)
                                  } else {
                                    newSelected.add(result.index)
                                  }
                                  setSelectedFailedIndices(newSelected)
                                }}
                                className="mr-2"
                              />
                            )}
                            <span className="text-xs font-medium text-muted-foreground">
                              Query #{result.index + 1}
                            </span>
                            {result.status === "success" && (
                              <Badge variant="default" className="text-xs">
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Success ({result.result_count} rows)
                              </Badge>
                            )}
                            {result.status !== "success" && (
                              <Badge variant="destructive" className="text-xs">
                                <XCircle className="h-3 w-3 mr-1" />
                                Failed
                              </Badge>
                            )}
                          </div>
                          {result.question && (
                            <p className="text-sm font-medium mb-2">{result.question}</p>
                          )}
                        </div>
                      </div>

                      {result.status !== "success" && result.error && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Error:</p>
                          <p className="text-xs text-red-600 bg-red-50 p-2 rounded">
                            {result.error}
                          </p>
                        </div>
                      )}

                      {result.status === "success" && result.sample_result && result.sample_result.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">
                            Sample Results:
                          </p>
                          <div className="text-xs bg-green-50 p-2 rounded max-h-40 overflow-y-auto">
                            <div className="overflow-x-auto">
                              <table className="min-w-full text-xs">
                                <thead>
                                  <tr className="border-b">
                                    {Object.keys(result.sample_result[0]).map((key) => (
                                      <th key={key} className="text-left p-1 font-medium">{key}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {result.sample_result.slice(0, 3).map((row: any, idx: number) => (
                                    <tr key={idx} className="border-b">
                                      {Object.values(row).map((val: any, colIdx: number) => (
                                        <td key={colIdx} className="p-1">{String(val)}</td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* New Questions List */}
            {activeTab === "new" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Generated Questions</h3>
                {session.status === "processing" && (
                  <Badge variant="default" className="text-xs">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Processing...
                  </Badge>
                )}
              </div>
              {questions.length === 0 ? (
                <div className="text-center py-8 space-y-2">
                  {session.status === "processing" || session.status === "generating" ? (
                    <>
                      <Loader2 className="h-6 w-6 animate-spin text-blue-500 mx-auto" />
                      <p className="text-sm text-muted-foreground">
                        {session.current_step === "generating_questions" 
                          ? "Generating questions..." 
                          : session.current_step === "loading_context"
                          ? "Loading context..."
                          : "Processing..."}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No questions generated yet...
                    </p>
                  )}
                </div>
              ) : (
                questions.map((question) => (
                  <div
                    key={question.id}
                    className="border rounded-lg p-4 space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-medium text-muted-foreground">
                            #{question.question_index}
                          </span>
                          {question.execution_status === "success" && (
                            <Badge variant="default" className="text-xs">
                              <CheckCircle2 className="h-3 w-3 mr-1" />
                              Success
                            </Badge>
                          )}
                          {question.execution_status === "error" && (
                            <Badge variant="destructive" className="text-xs">
                              <XCircle className="h-3 w-3 mr-1" />
                              Failed ({question.retry_count} retries)
                            </Badge>
                          )}
                          {question.is_stored && (
                            <Badge variant="default" className="text-xs">
                              Stored
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm font-medium">{question.question_text}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedQuestion(
                          expandedQuestion === question.id ? null : question.id
                        )}
                      >
                        {expandedQuestion === question.id ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    </div>

                    {expandedQuestion === question.id && (
                      <div className="space-y-3 pt-3 border-t">
                        {question.generated_sql && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">SQL Query:</p>
                            <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                              {question.generated_sql}
                            </pre>
                          </div>
                        )}

                        {question.execution_result && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">
                              Execution Result ({Array.isArray(question.execution_result) ? question.execution_result.length : 0} rows):
                            </p>
                            <div className="text-xs bg-green-50 p-2 rounded max-h-40 overflow-y-auto">
                              {Array.isArray(question.execution_result) && question.execution_result.length > 0 ? (
                                <div className="space-y-1">
                                  {/* Show first few rows as table */}
                                  <div className="overflow-x-auto">
                                    <table className="min-w-full text-xs">
                                      <thead>
                                        <tr className="border-b">
                                          {Object.keys(question.execution_result[0]).map((key) => (
                                            <th key={key} className="text-left p-1 font-medium">{key}</th>
                                          ))}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {question.execution_result.slice(0, 10).map((row: any, idx: number) => (
                                          <tr key={idx} className="border-b">
                                            {Object.values(row).map((val: any, colIdx: number) => (
                                              <td key={colIdx} className="p-1">{String(val)}</td>
                                            ))}
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                  {question.execution_result.length > 10 && (
                                    <p className="text-muted-foreground mt-1">
                                      ... and {question.execution_result.length - 10} more rows
                                    </p>
                                  )}
                                </div>
                              ) : (
                                <pre>{JSON.stringify(question.execution_result, null, 2)}</pre>
                              )}
                            </div>
                          </div>
                        )}

                        {question.execution_error && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">Error:</p>
                            <p className="text-xs text-red-600 bg-red-50 p-2 rounded">
                              {question.execution_error}
                            </p>
                          </div>
                        )}

                        {question.execution_status === "success" && !question.is_stored && !question.user_approval && (
                          <div className="space-y-2">
                            <Textarea
                              placeholder="Optional feedback (optional)..."
                              value={feedback[question.id] || ""}
                              onChange={(e) => setFeedback({ ...feedback, [question.id]: e.target.value })}
                              className="text-xs"
                              rows={2}
                            />
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={() => handleApprove(question.id, "approved")}
                                className="flex-1"
                                disabled={loading || processingQuestion === question.id}
                              >
                                {processingQuestion === question.id ? (
                                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="h-4 w-4 mr-2" />
                                )}
                                Approve & Store
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleApprove(question.id, "rejected")}
                                className="flex-1"
                                disabled={loading || processingQuestion === question.id}
                              >
                                {processingQuestion === question.id ? (
                                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                  <XCircle className="h-4 w-4 mr-2" />
                                )}
                                Reject
                              </Button>
                            </div>
                          </div>
                        )}
                        
                        {question.execution_status === "error" && question.retry_count >= 3 && (
                          <div className="text-xs text-muted-foreground bg-yellow-50 p-2 rounded">
                            This question failed after {question.retry_count} attempts. You can still review the SQL query.
                          </div>
                        )}

                        {question.user_approval && (
                          <div className="text-xs">
                            <Badge variant={question.user_approval === "approved" ? "default" : "destructive"}>
                              {question.user_approval}
                            </Badge>
                            {question.user_feedback && (
                              <p className="mt-1 text-muted-foreground">{question.user_feedback}</p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}

              {/* Summary when completed */}
              {session.status === "completed" && questions.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 mt-4">
                  <h4 className="font-medium text-sm mb-3">Session Summary</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Total Generated</p>
                      <p className="text-lg font-semibold">{session.total_questions_generated}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Successful</p>
                      <p className="text-lg font-semibold text-green-600">{session.successful_questions}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Failed</p>
                      <p className="text-lg font-semibold text-red-600">{session.failed_questions}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Stored</p>
                      <p className="text-lg font-semibold text-blue-600">{session.stored_questions}</p>
                    </div>
                  </div>
                  {session.success_rate !== null && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Overall Success Rate</span>
                        <span className="text-xs font-medium">{(session.success_rate * 100).toFixed(1)}%</span>
                      </div>
                      <Progress value={session.success_rate * 100} />
                    </div>
                  )}
                  {questions.filter(q => q.execution_status === "success" && !q.is_stored && !q.user_approval).length > 0 && (
                    <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded">
                      <p className="text-xs text-yellow-800">
                        {questions.filter(q => q.execution_status === "success" && !q.is_stored && !q.user_approval).length} successful question(s) are waiting for your approval.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
            )}

            <div className="flex justify-between items-center pt-4 border-t">
              <div className="text-xs text-muted-foreground">
                {session.status === "completed" && (
                  <span>
                    Session completed. {session.stored_questions} question(s) stored in use case.
                  </span>
                )}
                {session.status === "processing" && (
                  <span>Processing in progress...</span>
                )}
                {session.status === "paused" && (
                  <span>Session paused. Click Resume to continue.</span>
                )}
                {session.status === "generating" && (
                  <span>Initializing maturation process...</span>
                )}
                {improving && (
                  <span className="text-blue-600 font-medium">
                    {improvementStatus || "Improving use case with AI..."}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {session.status === "completed" && !improving && (
                  <Button
                    variant="default"
                    onClick={async () => {
                      if (!session || !useCase) return
                      
                      setImproving(true)
                      setImprovementStatus("Collecting feedback...")
                      
                      try {
                        // Step 1: Collect feedback
                        const feedbackResponse = await axios.post(
                          `/api/maturation/sessions/${session.id}/collect-feedback`,
                          {
                            session_id: session.id,
                            user_feedback: null,
                            approved_questions: questions
                              .filter(q => q.user_approval === "approved")
                              .map(q => q.id),
                            rejected_questions: questions
                              .filter(q => q.user_approval === "rejected")
                              .map(q => q.id),
                            improvement_suggestions: null
                          }
                        )
                        
                        setImprovementStatus("Improving use case with AI...")
                        
                        // Step 2: Improve use case
                        const improveResponse = await axios.post(
                          `/api/maturation/use-cases/${useCase.id}/improve`,
                          {
                            use_case_id: useCase.id,
                            maturation_results: feedbackResponse.data.maturation_results,
                            user_feedback: null,
                            improvement_suggestions: null
                          }
                        )
                        
                        const startedAt = improveResponse.data.started_at
                        const maxPollingTime = 5 * 60 * 1000 // 5 minutes max
                        const startPollingTime = Date.now()
                        let pollAttempts = 0
                        const maxPollAttempts = 100 // Max 100 attempts (about 5 minutes)
                        
                        // Poll for completion
                        setImprovementStatus("Waiting for AI to improve use case...")
                        
                        const checkCompletion = async () => {
                          pollAttempts++
                          
                          // Check timeout
                          if (Date.now() - startPollingTime > maxPollingTime || pollAttempts > maxPollAttempts) {
                            setImprovementStatus("Improvement is taking longer than expected. Please check back later.")
                            setTimeout(() => {
                              setImproving(false)
                              setImprovementStatus(null)
                              alert("Improvement is still in progress. The use case will be updated when complete.")
                            }, 3000)
                            return
                          }
                          
                          try {
                            const statusResponse = await axios.get(
                              `/api/maturation/use-cases/${useCase.id}/improvement-status`,
                              { params: { started_at: startedAt } }
                            )
                            
                            if (statusResponse.data.status === "completed") {
                              setImprovementStatus("Use case improved successfully!")
                              setTimeout(() => {
                                setImproving(false)
                                setImprovementStatus(null)
                                onComplete()
                                alert("Use case has been improved based on maturation results!")
                              }, 2000)
                            } else if (statusResponse.data.status === "processing") {
                              // Continue polling
                              setImprovementStatus(`Improving use case... (checking ${pollAttempts})`)
                              setTimeout(checkCompletion, 3000) // Check every 3 seconds
                            } else if (statusResponse.data.status === "error") {
                              throw new Error(statusResponse.data.message || "Error during improvement")
                            } else {
                              // Unknown status, continue polling
                              setTimeout(checkCompletion, 5000)
                            }
                          } catch (pollError: any) {
                            console.error("Error checking improvement status:", pollError)
                            // Continue polling even on error (might be temporary) but with longer delay
                            if (pollAttempts < maxPollAttempts) {
                              setTimeout(checkCompletion, 5000) // Retry after 5 seconds
                            } else {
                              setImprovementStatus("Error checking status. Please refresh the page.")
                              setImproving(false)
                              setImprovementStatus(null)
                            }
                          }
                        }
                        
                        // Start polling after 2 seconds
                        setTimeout(checkCompletion, 2000)
                        
                      } catch (error: any) {
                        console.error("Failed to improve use case:", error)
                        alert(`Failed to improve use case: ${error.response?.data?.detail || error.message}`)
                        setImproving(false)
                        setImprovementStatus(null)
                      }
                    }}
                    disabled={improving || loading}
                  >
                    {improving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Improving...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Improve Use Case with AI
                      </>
                    )}
                  </Button>
                )}
                {session.status === "completed" && questions.filter(q => q.execution_status === "success" && !q.is_stored && !q.user_approval).length > 0 && !improving && (
                  <Button
                    variant="default"
                    onClick={async () => {
                      const successfulQuestions = questions.filter(q => 
                        q.execution_status === "success" && !q.is_stored && !q.user_approval
                      )
                      setLoading(true)
                      try {
                        for (const q of successfulQuestions) {
                          await handleApprove(q.id, "approved")
                        }
                        onComplete()
                      } catch (error) {
                        console.error("Failed to approve all:", error)
                        alert("Failed to approve all questions. Please try again.")
                      } finally {
                        setLoading(false)
                      }
                    }}
                    disabled={loading}
                  >
                    {loading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                    )}
                    Approve All Successful ({questions.filter(q => q.execution_status === "success" && !q.is_stored && !q.user_approval).length})
                  </Button>
                )}
                {session.status === "completed" && !improving && (
                  <Button onClick={() => {
                    setSession(null)
                    setQuestions([])
                    setExpandedQuestion(null)
                    setFeedback({})
                    setExistingTestResults(null)
                    setAnalysis(null)
                    setSelectedFailedIndices(new Set())
                    setActiveTab("new")
                    setImproving(false)
                    setImprovementStatus(null)
                    createSession()
                  }} variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Start New Session
                  </Button>
                )}
                <Button onClick={onClose} variant={session.status === "completed" && !improving ? "default" : "outline"} disabled={improving}>
                  {session.status === "completed" ? "Done" : "Close"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

