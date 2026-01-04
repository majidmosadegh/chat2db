"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ThemeToggle } from "@/components/ui/theme-toggle"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Brain,
  Database,
  Search,
  FileText,
  Network,
  Target,
  Sparkles,
  Zap,
  TestTube,
  BarChart3,
  FileSearch,
  Shield,
  ChevronDown,
  ChevronRight,
  Settings,
  BookOpen,
  Link as LinkIcon,
  Lightbulb,
  Cpu,
  Activity,
  Eye,
  Lock,
  Menu,
  X,
  Wrench,
  TrendingUp,
  MessageCircle
} from "lucide-react"
import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"

interface NavigationItem {
  name: string
  href: string
  icon: any
  permissions: string[]
  badge?: string
  comingSoon?: boolean
  children?: NavigationItem[]
}

interface NavigationGroup {
  title: string
  icon: any
  items: NavigationItem[]
}

const navigationGroups: NavigationGroup[] = [
  {
    title: "Core Management",
    icon: Wrench,
    items: [
      {
        name: "Model Settings",
        href: "/models",
        icon: Brain,
        permissions: ["admin", "manager"]
      },
      {
        name: "Database Connection",
        href: "/database",
        icon: Database,
        permissions: ["admin", "manager"]
      },
      {
        name: "Schema Explorer",
        href: "/schema",
        icon: Search,
        permissions: ["admin", "manager", "analyst"]
      }
    ]
  },
  {
    title: "Data & Relationships",
    icon: BarChart3,
    items: [
      {
        name: "Data Dictionary",
        href: "/data-dictionary",
        icon: BookOpen,
        permissions: ["admin", "manager", "analyst"]
      },
      {
        name: "Relationships",
        href: "/relationships",
        icon: Network,
        permissions: ["admin", "manager"]
      },
      {
        name: "Use Cases",
        href: "/use-cases",
        icon: Lightbulb,
        permissions: ["admin", "manager", "analyst"]
      }
    ]
  },
  {
    title: "Smart Tools",
    icon: Sparkles,
    items: [
      {
        name: "Chat Assistant",
        href: "/chat",
        icon: MessageCircle,
        permissions: ["admin", "manager", "analyst"],
        badge: "Beta"
      },
      {
        name: "Smart Use Case Builder",
        href: "/smart-use-case-builder",
        icon: Sparkles,
        permissions: ["admin", "manager"],
        badge: "AI"
      },
      {
        name: "Prompt Generator",
        href: "/prompt-generator",
        icon: FileText,
        permissions: ["admin", "manager"]
      },
      {
        name: "Testing & Validation",
        href: "/testing-validation",
        icon: TestTube,
        permissions: ["admin", "manager"],
        comingSoon: true
      }
    ]
  },
  {
    title: "Monitoring & Reports",
    icon: TrendingUp,
    items: [
      {
        name: "Performance Dashboard",
        href: "/performance-dashboard",
        icon: BarChart3,
        permissions: ["admin"],
        comingSoon: true
      },
      {
        name: "Logs & Events",
        href: "/logs-events",
        icon: FileSearch,
        permissions: ["admin"],
        comingSoon: true
      },
      {
        name: "Security & Access",
        href: "/security-access",
        icon: Shield,
        permissions: ["admin"],
        comingSoon: true
      }
    ]
  }
]

// Mock user permissions - در آینده از authentication system می‌آید
const userPermissions = ["admin", "manager", "analyst"]

function NavigationItem({ item, pathname, onNavigate }: { item: NavigationItem; pathname: string; onNavigate?: () => void }) {
  const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
  const hasPermission = userPermissions.some(permission => item.permissions.includes(permission))

  if (!hasPermission) return null

  const handleClick = (e: React.MouseEvent) => {
    if (item.comingSoon) {
      e.preventDefault()
      return
    }
    onNavigate?.()
  }

  return (
    <Link
      href={item.comingSoon ? "#" : item.href}
      className={cn(
        "flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
        item.comingSoon && "cursor-not-allowed opacity-60",
        isActive && !item.comingSoon
          ? "bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100"
          : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
      )}
      onClick={handleClick}
    >
      <div className="flex items-center">
        <item.icon className="mr-3 h-5 w-5 flex-shrink-0" />
        <span className="truncate">{item.name}</span>
      </div>
      <div className="flex items-center gap-2">
        {item.badge && (
          <Badge variant="secondary" className="text-xs px-1.5 py-0.5">
            {item.badge}
          </Badge>
        )}
      </div>
    </Link>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    "Core Management": true,
    "Data & Relationships": false,
    "Smart Tools": false,
    "Monitoring & Reports": false
  })

  const toggleGroup = (title: string) => {
    setExpandedGroups(prev => {
      const newState: Record<string, boolean> = {}
      // Close all groups first
      Object.keys(prev).forEach(key => {
        newState[key] = false
      })
      // Open the clicked group (unless it was already open, then close it)
      newState[title] = !prev[title]
      return newState
    })
  }

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false)
  }

  return (
    <>
      {/* Mobile Menu Button */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex h-16 items-center justify-between bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 shadow-sm">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">SQL</span>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white truncate">Text-to-SQL</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Admin Panel</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden"
            aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black bg-opacity-50 backdrop-blur-sm"
          onClick={closeMobileMenu}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed inset-y-0 left-0 z-40 flex h-screen w-64 max-w-[85vw] flex-col bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 shadow-lg transition-transform duration-300 ease-in-out",
        // Desktop: always visible
        "md:translate-x-0 md:block",
        // Mobile: slide in/out
        "hidden",
        isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        {/* Desktop Header */}
        <div className="hidden md:flex h-16 items-center justify-between border-b border-gray-200 dark:border-gray-800 px-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">SQL</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Text-to-SQL</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Admin Panel</p>
            </div>
          </div>
          <ThemeToggle />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4">
          <div className="space-y-6">
            {navigationGroups.map((group) => (
              <div key={group.title} className="space-y-1">
                {/* Group Header */}
                <button
                  onClick={() => toggleGroup(group.title)}
                  className="flex items-center justify-between w-full px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <group.icon className="h-4 w-4 flex-shrink-0" />
                    <span className="truncate">{group.title}</span>
                  </div>
                  {expandedGroups[group.title] ? (
                    <ChevronDown className="h-4 w-4 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 flex-shrink-0" />
                  )}
                </button>

                {/* Group Items */}
                {expandedGroups[group.title] && (
                  <div className="space-y-1 ml-2">
                    {group.items.map((item) => (
                      <NavigationItem
                        key={item.name}
                        item={item}
                        pathname={pathname}
                        onNavigate={closeMobileMenu}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="mt-auto p-2 border-t border-gray-200 dark:border-gray-800">
          <div className="text-xs text-gray-400 dark:text-gray-500 text-center font-mono pb-1">
            v1.0.0
          </div>
        </div>

      </div>
    </>
  )
}
