"use client"

import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"

interface PageTransitionProps {
  children: React.ReactNode
  className?: string
}

export function PageTransition({ children, className }: PageTransitionProps) {
  const pathname = usePathname()
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    const timer = setTimeout(() => setIsLoading(false), 150)
    return () => clearTimeout(timer)
  }, [pathname])

  return (
    <div
      className={cn(
        "transition-all duration-300 ease-in-out",
        isLoading
          ? "opacity-0 transform translate-y-2"
          : "opacity-100 transform translate-y-0",
        className
      )}
    >
      {children}
    </div>
  )
}

interface RouteTransitionProps {
  children: React.ReactNode
  className?: string
}

export function RouteTransition({ children, className }: RouteTransitionProps) {
  const pathname = usePathname()
  const [displayChildren, setDisplayChildren] = useState(children)
  const [transitionStage, setTransitionStage] = useState("fadeIn")

  useEffect(() => {
    setTransitionStage("fadeOut")
  }, [pathname])

  useEffect(() => {
    if (transitionStage === "fadeOut") {
      const timer = setTimeout(() => {
        setDisplayChildren(children)
        setTransitionStage("fadeIn")
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [transitionStage, children])

  return (
    <div
      className={cn(
        "transition-all duration-300 ease-in-out",
        transitionStage === "fadeIn"
          ? "opacity-100 transform translate-x-0"
          : "opacity-0 transform translate-x-4",
        className
      )}
    >
      {displayChildren}
    </div>
  )
}

// Hook for programmatic transitions
export function usePageTransition() {
  const [isTransitioning, setIsTransitioning] = useState(false)

  const startTransition = () => {
    setIsTransitioning(true)
    setTimeout(() => setIsTransitioning(false), 300)
  }

  return { isTransitioning, startTransition }
}

// Higher-order component for transition effects
export function withTransition<P extends object>(
  Component: React.ComponentType<P>,
  transitionType: "fade" | "slide" | "scale" = "fade"
) {
  return function WrappedComponent(props: P) {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
      setMounted(true)
    }, [])

    const transitionClasses = {
      fade: mounted ? "opacity-100" : "opacity-0",
      slide: mounted ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0",
      scale: mounted ? "scale-100 opacity-100" : "scale-95 opacity-0",
    }

    return (
      <div className={cn(
        "transition-all duration-300 ease-in-out",
        transitionClasses[transitionType]
      )}>
        <Component {...props} />
      </div>
    )
  }
}














