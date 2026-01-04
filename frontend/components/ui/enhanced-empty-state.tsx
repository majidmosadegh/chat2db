import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

interface EnhancedEmptyStateProps {
  icon?: LucideIcon
  title: string
  description: string
  variant?: "default" | "minimal" | "card" | "hero"
  actions?: {
    primary?: {
      label: string
      onClick: () => void
      variant?: "default" | "outline" | "secondary" | "ghost" | "link" | "destructive"
      icon?: LucideIcon
    }
    secondary?: {
      label: string
      onClick: () => void
      variant?: "default" | "outline" | "secondary" | "ghost" | "link" | "destructive"
      icon?: LucideIcon
    }
  }
  className?: string
  illustration?: React.ReactNode
}

export function EnhancedEmptyState({
  icon: Icon,
  title,
  description,
  variant = "default",
  actions,
  className,
  illustration
}: EnhancedEmptyStateProps) {
  const variantStyles = {
    default: "py-12",
    minimal: "py-8",
    card: "p-8 border rounded-lg bg-card",
    hero: "py-24"
  }

  const iconStyles = {
    default: "h-12 w-12",
    minimal: "h-8 w-8",
    card: "h-16 w-16",
    hero: "h-24 w-24"
  }

  const titleStyles = {
    default: "text-xl",
    minimal: "text-lg",
    card: "text-2xl",
    hero: "text-4xl"
  }

  return (
    <div className={cn(
      "flex flex-col items-center justify-center text-center",
      variantStyles[variant],
      className
    )}>
      {/* Illustration or Icon */}
      {illustration ? (
        <div className="mb-6 animate-fade-in">
          {illustration}
        </div>
      ) : Icon && (
        <div className={cn(
          "mb-6 rounded-full bg-gradient-to-br from-primary/10 to-primary/5 p-4 animate-scale-in",
          variant === "hero" && "p-6"
        )}>
          <Icon className={cn(
            "text-primary animate-fade-in",
            iconStyles[variant]
          )} />
        </div>
      )}

      {/* Title */}
      <h3 className={cn(
        "font-semibold text-foreground mb-2 animate-fade-in",
        titleStyles[variant]
      )}>
        {title}
      </h3>

      {/* Description */}
      <p className={cn(
        "text-muted-foreground mb-8 max-w-md animate-fade-in",
        variant === "minimal" ? "text-sm" : "text-base",
        "[animation-delay:100ms]"
      )}>
        {description}
      </p>

      {/* Actions */}
      {actions && (
        <div className={cn(
          "flex gap-3 animate-fade-in",
          "[animation-delay:200ms]"
        )}>
          {actions.primary && (
            <Button
              onClick={actions.primary.onClick}
              variant={actions.primary.variant || "default"}
              className="gap-2"
            >
              {actions.primary.icon && <actions.primary.icon className="h-4 w-4" />}
              {actions.primary.label}
            </Button>
          )}
          {actions.secondary && (
            <Button
              onClick={actions.secondary.onClick}
              variant={actions.secondary.variant || "outline"}
              className="gap-2"
            >
              {actions.secondary.icon && <actions.secondary.icon className="h-4 w-4" />}
              {actions.secondary.label}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

// Specialized empty states for common use cases
export function NoDataState({ onRefresh }: { onRefresh?: () => void }) {
  return (
    <EnhancedEmptyState
      title="No data available"
      description="There is no data to display at the moment. Try refreshing or check back later."
      actions={onRefresh ? {
        primary: {
          label: "Refresh",
          onClick: onRefresh
        }
      } : undefined}
    />
  )
}

export function NoResultsState({ onClearFilters }: { onClearFilters?: () => void }) {
  return (
    <EnhancedEmptyState
      title="No results found"
      description="We couldn't find any results matching your search criteria. Try adjusting your filters or search terms."
      actions={onClearFilters ? {
        primary: {
          label: "Clear filters",
          onClick: onClearFilters
        }
      } : undefined}
    />
  )
}

export function ErrorState({
  title = "Something went wrong",
  description = "An error occurred while loading this content. Please try again.",
  onRetry
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <EnhancedEmptyState
      title={title}
      description={description}
      actions={onRetry ? {
        primary: {
          label: "Try again",
          onClick: onRetry
        }
      } : undefined}
    />
  )
}














