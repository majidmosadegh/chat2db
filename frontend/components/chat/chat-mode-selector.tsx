"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Database, HelpCircle, MessageSquare, BarChart3 } from "lucide-react"

export type ChatMode = 'sql_question' | 'explain_result' | 'meta_question' | 'help_error'

interface ChatModeOption {
  id: ChatMode
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  color: string
}

const CHAT_MODE_OPTIONS: ChatModeOption[] = [
  {
    id: 'sql_question',
    title: 'پرسش SQL',
    description: 'پرسیدن سوال درباره داده‌ها و اجرای کوئری‌های SQL',
    icon: Database,
    color: 'bg-blue-500'
  },
  {
    id: 'meta_question',
    title: 'پرسش درباره داده‌ها',
    description: 'پرسیدن سوال درباره ساختار داده‌ها، جداول و فیلدها',
    icon: MessageSquare,
    color: 'bg-green-500'
  },
  {
    id: 'explain_result',
    title: 'توضیح نتیجه',
    description: 'دریافت توضیح درباره نتایج کوئری‌های قبلی',
    icon: BarChart3,
    color: 'bg-purple-500'
  },
  {
    id: 'help_error',
    title: 'کمک و رفع خطا',
    description: 'دریافت کمک برای نوشتن کوئری یا رفع خطاهای SQL',
    icon: HelpCircle,
    color: 'bg-orange-500'
  }
]

interface ChatModeSelectorProps {
  onModeSelect: (mode: ChatMode) => void
  selectedMode?: ChatMode | null
}

export function ChatModeSelector({ onModeSelect, selectedMode }: ChatModeSelectorProps) {
  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Select Chat Type
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Each chat type is designed for a specific purpose
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CHAT_MODE_OPTIONS.map((option) => {
            const Icon = option.icon
            const isSelected = selectedMode === option.id

            return (
              <Card
                key={option.id}
                className={`cursor-pointer transition-all duration-200 hover:shadow-lg ${
                  isSelected
                    ? 'ring-2 ring-blue-500 shadow-lg'
                    : 'hover:shadow-md'
                }`}
                onClick={() => onModeSelect(option.id)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 ${option.color} rounded-lg flex items-center justify-center`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{option.title}</CardTitle>
                      {isSelected && (
                        <span className="text-sm text-blue-600 dark:text-blue-400 font-medium">
                          Selected
                        </span>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm">
                    {option.description}
                  </CardDescription>
                  <Button
                    className="w-full mt-4"
                    variant={isSelected ? "default" : "outline"}
                    onClick={(e) => {
                      e.stopPropagation()
                      onModeSelect(option.id)
                    }}
                  >
                    {isSelected ? 'Selected' : 'Select'}
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {selectedMode && (
          <div className="text-center mt-8">
            <Button
              size="lg"
              onClick={() => {
                // This will trigger the next step (snapshot selection)
                const event = new CustomEvent('chatModeSelected', { detail: selectedMode })
                window.dispatchEvent(event)
              }}
            >
              ادامه به انتخاب پایگاه داده
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}














