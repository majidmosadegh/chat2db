"use client"

import * as React from "react"
import { Moon, Sun, Monitor } from "lucide-react"
import { useTheme } from "next-themes"

const themeIcons = {
  light: Sun,
  dark: Moon,
  system: Monitor,
}

const themeOrder = ["light", "dark", "system"] as const

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const cycleTheme = () => {
    const currentIndex = themeOrder.indexOf((theme as typeof themeOrder[number]) || "system")
    const nextIndex = (currentIndex + 1) % themeOrder.length
    setTheme(themeOrder[nextIndex])
  }

  if (!mounted) {
    return (
      <button className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors">
        <Monitor className="h-4 w-4" />
      </button>
    )
  }

  const currentTheme = (theme as keyof typeof themeIcons) || "system"
  const Icon = themeIcons[currentTheme]

  return (
    <button
      onClick={cycleTheme}
      className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
      title={`Current theme: ${currentTheme}. Click to cycle themes.`}
    >
      <Icon className="h-4 w-4 transition-all duration-200" />
    </button>
  )
}














