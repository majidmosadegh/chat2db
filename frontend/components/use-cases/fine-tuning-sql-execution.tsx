"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Loader2, Play, CheckCircle, XCircle, ThumbsUp, ThumbsDown, Database, Code } from "lucide-react"
import axios from "axios"

interface Question {
  id: number
  question_index: number
  question_text: string
  is_user_edited: boolean
  generated_sql: string | null
  execution_status: string | null
  execution_result: string | null
  execution_error: string | null
  user_approval: string | null
  user_feedback: string | null
}

interface FineTuningSQLExecutionProps {
  sessionId: number
  onNext: () => void
}

export function FineTuningSQLExecution({ sessionId, onNext }: FineTuningSQLExecutionProps) {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [processingQuestion, setProcessingQuestion] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<{ [key: number]: string }>({})

  useEffect(() => {
    fetchQuestions()
  }, [sessionId])

  // Auto-generate SQL for questions that don't have it
  useEffect(() => {
    const generateMissingSQL = async () => {
      for (const question of questions) {
        if (!question.generated_sql && !processingQuestion) {
          await handleGenerateSQL(question.id)
          break // Only process one at a time
        }
      }
    }

    if (questions.length > 0 && !processingQuestion) {
      generateMissingSQL()
    }
  }, [questions, processingQuestion])

  // Auto-execute SQL for questions that have SQL but no results
  useEffect(() => {
    const executePendingSQL = async () => {
      for (const question of questions) {
        if (question.generated_sql && !question.execution_result && !question.execution_error && !processingQuestion) {
          await handleExecuteSQL(question.id)
          break // Only process one at a time
        }
      }
    }

    if (questions.length > 0 && !processingQuestion) {
      executePendingSQL()
    }
  }, [questions, processingQuestion])

  const fetchQuestions = async () => {
    try {
      const response = await axios.get(`/api/fine-tuning/sessions/${sessionId}/questions`)
      setQuestions(response.data)
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateSQL = async (questionId: number) => {
    setProcessingQuestion(questionId)
    try {
      await axios.post(`/api/fine-tuning/questions/${questionId}/generate-sql`)
      // SQL will be updated via polling
      await fetchQuestions()
    } catch (error) {
    } finally {
      setProcessingQuestion(null)
    }
  }

  const handleExecuteSQL = async (questionId: number) => {
    setProcessingQuestion(questionId)
    try {
      await axios.post(`/api/fine-tuning/questions/${questionId}/execute`)
      // Results will be updated via polling
      await fetchQuestions()
    } catch (error) {
    } finally {
      setProcessingQuestion(null)
    }
  }

  const handleSubmitFeedback = async (questionId: number, approval: string) => {
    try {
      await axios.post(`/api/fine-tuning/questions/${questionId}/feedback`, {
        approval,
        feedback: feedback[questionId] || ""
      })
      await fetchQuestions()
    } catch (error) {
    }
  }

  const getStatusIcon = (status: string | null) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "executing":
      case "generating_sql":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      default:
        return <Play className="h-4 w-4 text-gray-400" />
    }
  }

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case "success":
        return <Badge className="bg-green-100 text-green-800">Success</Badge>
      case "error":
        return <Badge className="bg-red-100 text-red-800">Error</Badge>
      case "executing":
        return <Badge className="bg-blue-100 text-blue-800">Executing</Badge>
      case "generating_sql":
        return <Badge className="bg-blue-100 text-blue-800">Generating SQL</Badge>
      case "sql_generated":
        return <Badge className="bg-yellow-100 text-yellow-800">SQL Ready</Badge>
      default:
        return <Badge variant="outline">Pending</Badge>
    }
  }

  const formatExecutionResult = (result: string | null) => {
    if (!result) return null

    try {
      const data = JSON.parse(result)
      if (Array.isArray(data) && data.length > 0) {
        // Take first 5 rows for display
        const displayData = data.slice(0, 5)
        return displayData
      }
    } catch (e) {
      return null
    }
    return null
  }

  const allQuestionsProcessed = questions.length > 0 &&
    questions.every(q => q.user_approval === "approved" || q.user_approval === "rejected")

  // Auto-advance when all questions are processed
  useEffect(() => {
    if (allQuestionsProcessed) {
      setTimeout(() => {
        onNext()
      }, 1000)
    }
  }, [allQuestionsProcessed, onNext])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading questions...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">SQL Generation & Execution</h2>
        <p className="text-muted-foreground">
          Generate SQL queries for each question, execute them, and provide feedback
        </p>
      </div>

      {/* Progress Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Progress Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{questions.length}</div>
              <div className="text-sm text-muted-foreground">Total Questions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {questions.filter(q => q.execution_status === "success").length}
              </div>
              <div className="text-sm text-muted-foreground">Successful Executions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {questions.filter(q => q.execution_status === "error").length}
              </div>
              <div className="text-sm text-muted-foreground">Failed Executions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {questions.filter(q => q.user_approval).length}
              </div>
              <div className="text-sm text-muted-foreground">Reviewed</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Questions List */}
      <div className="space-y-4">
        {questions.map((question, index) => (
          <Card key={question.id} className="border-l-4 border-l-green-500">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">Question {index + 1}</Badge>
                  {getStatusBadge(question.execution_status)}
                </div>
                <div className="flex items-center gap-2">
                  {getStatusIcon(question.execution_status)}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Question Text */}
              <div>
                <h4 className="font-semibold mb-2">Question:</h4>
                <p className="text-sm bg-gray-50 p-3 rounded">{question.question_text}</p>
              </div>

              {/* SQL Generation */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold flex items-center gap-2">
                    <Code className="h-4 w-4" />
                    Generated SQL
                  </h4>
                  {!question.generated_sql && (
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleGenerateSQL(question.id)}
                        disabled={processingQuestion === question.id}
                        className="gap-2"
                      >
                        {processingQuestion === question.id && <Loader2 className="h-3 w-3 animate-spin" />}
                        Generate SQL
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await axios.post(`/api/fine-tuning/questions/${question.id}/force-complete-sql`)
                            alert("✅ SQL نمونه اضافه شد!")
                            // Refresh questions
                            setTimeout(() => fetchQuestions(), 1000)
                          } catch (error) {
                            alert("❌ خطا: " + (error as any).response?.data?.detail || (error as any).message)
                          }
                        }}
                        className="gap-2 bg-green-600 hover:bg-green-700"
                      >
                        SQL نمونه
                      </Button>
                    </div>
                  )}
                </div>

                {question.generated_sql ? (
                  <pre className="bg-gray-900 text-green-400 p-3 rounded text-sm overflow-x-auto">
                    <code>{question.generated_sql}</code>
                  </pre>
                ) : (
                  <div className="bg-gray-50 p-3 rounded text-sm text-muted-foreground">
                    SQL not generated yet
                  </div>
                )}
              </div>

              {/* Execution Results */}
              {question.generated_sql && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold">Execution Results</h4>
                    {!question.execution_result && !question.execution_error && (
                      <Button
                        size="sm"
                        onClick={() => handleExecuteSQL(question.id)}
                        disabled={processingQuestion === question.id}
                        className="gap-2"
                      >
                        {processingQuestion === question.id && <Loader2 className="h-3 w-3 animate-spin" />}
                        <Play className="h-3 w-3" />
                        Execute Query
                      </Button>
                    )}
                  </div>

                  {question.execution_result && (
                    <div className="space-y-2">
                      <Badge className="bg-green-100 text-green-800">Query executed successfully</Badge>
                      {(() => {
                        const formattedResult = formatExecutionResult(question.execution_result)
                        return formattedResult ? (
                          <div className="border rounded max-h-48 overflow-y-auto">
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  {Object.keys(formattedResult[0]).map((col) => (
                                    <TableHead key={col} className="text-xs">{col}</TableHead>
                                  ))}
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {formattedResult.map((row, i) => (
                                  <TableRow key={i}>
                                    {Object.values(row).map((value, j) => (
                                      <TableCell key={j} className="text-xs font-mono">
                                        {String(value)}
                                      </TableCell>
                                    ))}
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        ) : (
                          <div className="bg-gray-50 p-3 rounded text-sm">
                            Query returned results (preview not available)
                          </div>
                        )
                      })()}
                    </div>
                  )}

                  {question.execution_error && (
                    <div className="bg-red-50 border border-red-200 rounded p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <XCircle className="h-4 w-4 text-red-500" />
                        <span className="font-semibold text-red-800">Execution Error</span>
                      </div>
                      <p className="text-sm text-red-700 font-mono">{question.execution_error}</p>
                    </div>
                  )}
                </div>
              )}

              {/* User Feedback */}
              {(question.execution_result || question.execution_error) && (
                <div>
                  <h4 className="font-semibold mb-2">Your Feedback</h4>

                  {!question.user_approval ? (
                    <div className="space-y-3">
                      <Textarea
                        placeholder="Optional feedback about this SQL generation..."
                        value={feedback[question.id] || ""}
                        onChange={(e) => setFeedback(prev => ({
                          ...prev,
                          [question.id]: e.target.value
                        }))}
                        className="min-h-[60px]"
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleSubmitFeedback(question.id, "approved")}
                          className="gap-2 bg-green-600 hover:bg-green-700"
                        >
                          <ThumbsUp className="h-4 w-4" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSubmitFeedback(question.id, "rejected")}
                          className="gap-2 border-red-200 text-red-600 hover:bg-red-50"
                        >
                          <ThumbsDown className="h-4 w-4" />
                          Reject
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Badge className={question.user_approval === "approved" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}>
                        {question.user_approval === "approved" ? "Approved" : "Rejected"}
                      </Badge>
                      {question.user_feedback && (
                        <span className="text-sm text-muted-foreground">"{question.user_feedback}"</span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button variant="outline">
          Back
        </Button>
        <Button
          onClick={onNext}
          disabled={!allQuestionsProcessed}
          className="gap-2"
        >
          <CheckCircle className="h-4 w-4" />
          Continue to Use Case Refinement
        </Button>
      </div>
    </div>
  )
}
