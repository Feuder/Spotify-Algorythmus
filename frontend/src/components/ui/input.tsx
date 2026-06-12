import * as React from "react"
import { cn } from "@/lib/utils"

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn("h-10 w-full rounded-md border border-border bg-input px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary", className)}
      {...props}
    />
  )
}

