import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
    variant?: "default" | "outline" | "secondary" | "ghost" | "link" | "destructive"
  }
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className
}: EmptyStateProps) {
  return (
    <div className={cn(
      "flex flex-col items-center justify-center py-12 px-4 text-center",
      className
    )}>
      {Icon && (
        <div className="mb-4 rounded-full bg-muted p-3">
          <Icon className="h-8 w-8 text-muted-foreground" />
        </div>
      )}

      <h3 className="mb-2 text-lg font-semibold text-foreground">
        {title}
      </h3>

      <p className="mb-6 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>

      {action && (
        <Button
          onClick={action.onClick}
          variant={action.variant || "default"}
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}

interface EmptyTableProps {
  icon?: LucideIcon
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
  }
  columns?: number
}

export function EmptyTable({
  icon: Icon,
  title,
  description,
  action,
  columns = 5
}: EmptyTableProps) {
  return (
    <div className="py-12">
      <EmptyState
        icon={Icon}
        title={title}
        description={description}
        action={action}
      />
    </div>
  )
}














