import * as React from "react"
import { cn } from "@/lib/utils"

export function Badge({
  className,
  variant = "secondary",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: "secondary" | "outline" | "success" | "warning" }) {
  const variants = {
    secondary: "bg-secondary text-secondary-foreground",
    outline: "border border-border text-muted-foreground",
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-warning",
  }
  return (
    <span
      className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", variants[variant], className)}
      {...props}
    />
  )
}

