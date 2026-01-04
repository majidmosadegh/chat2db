"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Loader2, Edit, Plus, Trash2, Wand2, CheckCircle, ClipboardList } from "lucide-react"
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

interface FineTuningQuestionGenerationProps {
  sessionId: number
  onNext: () => void
}

export function FineTuningQuestionGeneration({ sessionId, onNext }: FineTuningQuestionGenerationProps) {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editText, setEditText] = useState("")

  useEffect(() => {
    fetchQuestions()
  }, [sessionId])

  // Auto-advance when questions are generated
  useEffect(() => {
    if (questions.length > 0 && !generating) {
      // Small delay to show the questions briefly
      setTimeout(() => {
        onNext()
      }, 1000)
    }
  }, [questions.length, generating, onNext])

  const fetchQuestions = async () => {
    try {
      const response = await axios.get(`/api/fine-tuning/sessions/${sessionId}/questions`)
      setQuestions(response.data)
      } catch (error) {
    }
  }

  // Refresh questions every few seconds while on this step
  useEffect(() => {
    if (loading) return

    const interval = setInterval(() => {
      fetchQuestions()
    }, 4000) // Check for new questions every 4 seconds

    return () => clearInterval(interval)
  }, [sessionId, loading])

  const handleGenerateQuestions = async () => {
    setGenerating(true)
    try {
      const response = await axios.post(`/api/fine-tuning/sessions/${sessionId}/generate-questions`)
      // Questions will be updated via polling in the parent component
    } catch (error) {
      alert(`Failed to generate questions: ${(error as any).response?.data?.detail || (error as any).message}`)
    } finally {
      setGenerating(false)
    }
  }

  // Auto-generate questions on component mount (only if no questions exist)
  useEffect(() => {
    if (!generating && questions.length === 0 && !loading) {
      setTimeout(() => handleGenerateQuestions(), 1000) // Small delay
    }
  }, [loading]) // Run when loading completes

  // Auto-advance when we have questions and generation is complete (only if more than 3 questions)
  useEffect(() => {
    if (questions.length >= 3 && !generating) {
      const timer = setTimeout(() => {
        onNext()
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [questions.length, generating, onNext])

  const handleSaveQuestions = async () => {
    const questionTexts = questions.map(q => q.question_text).filter(text => text.trim())
    try {
      await axios.put(`/api/fine-tuning/sessions/${sessionId}/questions`, {
        questions: questionTexts
      })
      setEditingIndex(null)
      setEditText("")
    } catch (error) {
    }
  }

  const handleEditQuestion = (index: number, currentText: string) => {
    setEditingIndex(index)
    setEditText(currentText)
  }

  const handleSaveEdit = () => {
    if (editingIndex !== null) {
      const updatedQuestions = [...questions]
      updatedQuestions[editingIndex] = {
        ...updatedQuestions[editingIndex],
        question_text: editText,
        is_user_edited: true
      }
      setQuestions(updatedQuestions)
      setEditingIndex(null)
      setEditText("")
    }
  }

  const handleCancelEdit = () => {
    setEditingIndex(null)
    setEditText("")
  }

  const handleAddQuestion = () => {
    const newQuestion: Question = {
      id: Date.now(), // Temporary ID
      question_index: questions.length,
      question_text: "New question...",
      is_user_edited: true,
      generated_sql: null,
      execution_status: null,
      execution_result: null,
      execution_error: null,
      user_approval: null,
      user_feedback: null
    }
    setQuestions([...questions, newQuestion])
    setEditingIndex(questions.length)
    setEditText("New question...")
  }

  const handleRemoveQuestion = (index: number) => {
    const updatedQuestions = questions.filter((_, i) => i !== index)
    setQuestions(updatedQuestions)
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">Question Generation</h2>
        <p className="text-muted-foreground">
          AI generates realistic business questions based on your use case and database schema
        </p>
      </div>

      {/* Generate Questions Button */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5" />
            Generate Questions
          </CardTitle>
          <CardDescription>
            Use AI to generate realistic business questions that can be answered with your database
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Button
              onClick={handleGenerateQuestions}
              disabled={generating}
              className="gap-2"
            >
              {generating && <Loader2 className="h-4 w-4 animate-spin" />}
              <Wand2 className="h-4 w-4" />
              تولید سوالات با AI
            </Button>
            <span className="text-sm text-muted-foreground">
              {questions.length > 0 ? `${questions.length} سوال تولید شده` : "در حال تولید سوالات..."}
            </span>
            {questions.length === 0 && generating && (
              <span className="text-sm text-orange-600">
                اگر AI پاسخ نداد، از دکمه "استفاده از سوالات نمونه" استفاده کنید
              </span>
            )}
            {questions.length === 0 && !generating && (
              <Button
                variant="default"
                size="sm"
                onClick={async () => {
                  try {
                    const response = await axios.post(`/api/fine-tuning/sessions/${sessionId}/force-complete-questions`)
                    alert("✅ سوالات نمونه اضافه شدند!")
                    // Refresh questions after a delay
                    setTimeout(() => fetchQuestions(), 1000)
                  } catch (error) {
                    alert("❌ خطا: " + (error as any).response?.data?.detail || (error as any).message)
                  }
                }}
                className="ml-2 bg-green-600 hover:bg-green-700"
              >
                📋 استفاده از سوالات نمونه
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Questions List */}
      {questions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Generated Questions ({questions.length})
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAddQuestion}
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Add Question
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveQuestions}
                  disabled={loading}
                >
                  {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Save Changes
                </Button>
              </div>
            </CardTitle>
            <CardDescription>
              Review and edit the generated questions. You can modify, add, or remove questions as needed.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {questions.map((question, index) => (
                <Card key={question.id || index} className="border-l-4 border-l-blue-500">
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">Question {index + 1}</Badge>
                        {question.is_user_edited && (
                          <Badge variant="secondary">Edited</Badge>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditQuestion(index, question.question_text)}
                          className="h-8 w-8 p-0"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveQuestion(index)}
                          className="h-8 w-8 p-0 text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {editingIndex === index ? (
                      <div className="space-y-2">
                        <Textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="min-h-[80px]"
                          placeholder="Enter your question..."
                        />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={handleSaveEdit}>
                            Save
                          </Button>
                          <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm">{question.question_text}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button variant="outline">
          Back
        </Button>
        <Button
          onClick={onNext}
          disabled={questions.length < 3}
          className="gap-2"
        >
          <CheckCircle className="h-4 w-4" />
ادامه به اجرای SQL ({questions.length} سوال)
        </Button>
      </div>
    </div>
  )
}
