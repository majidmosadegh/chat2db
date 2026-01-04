"use client"

import { usePathname } from "next/navigation"
import { Sidebar } from "./sidebar"

interface MainLayoutProps {
  children: React.ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  const pathname = usePathname()
  const isChatPage = pathname === '/chat'

  return (
    <div className={`${isChatPage ? 'h-screen overflow-hidden' : 'min-h-screen'} bg-gray-50 dark:bg-gray-950`}>
      <Sidebar />
      <main className={`md:ml-64 ${isChatPage ? 'h-screen overflow-hidden pt-0' : 'overflow-auto min-h-screen pt-16 md:pt-0'}`}>
        {isChatPage ? (
          children
        ) : (
          <div className="container mx-auto p-4 md:p-6 lg:p-8">
            {children}
          </div>
        )}
      </main>
    </div>
  )
}
