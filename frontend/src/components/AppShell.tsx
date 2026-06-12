import type { ReactNode } from "react"
import {
  AudioLines,
  Clock3,
  Database,
  Home,
  ListMusic,
  Settings,
  Sparkles,
  UserRound,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type View = "overview" | "generate" | "history" | "profiles" | "music" | "settings" | "system"

const navigation: Array<{ id: View; label: string; icon: typeof Home }> = [
  { id: "overview", label: "Übersicht", icon: Home },
  { id: "generate", label: "Playlist erstellen", icon: Sparkles },
  { id: "history", label: "Verlauf", icon: Clock3 },
  { id: "profiles", label: "Profile", icon: UserRound },
  { id: "music", label: "Musikdaten", icon: ListMusic },
  { id: "settings", label: "Einstellungen", icon: Settings },
  { id: "system", label: "System", icon: Database },
]

export function AppShell({
  view,
  onView,
  children,
}: {
  view: View
  onView: (view: View) => void
  children: ReactNode
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <AudioLines aria-hidden />
          <span>Resonanz</span>
        </div>
        <nav className="nav-list" aria-label="Hauptnavigation">
          {navigation.map((item) => {
            const Icon = item.icon
            return (
              <Button
                key={item.id}
                variant="ghost"
                className={cn("nav-item", view === item.id && "nav-item-active")}
                onClick={() => onView(item.id)}
              >
                <Icon data-icon="inline-start" aria-hidden />
                {item.label}
              </Button>
            )
          })}
        </nav>
        <div className="profile-tile">
          <span className="profile-avatar">DU</span>
          <div>
            <strong>Dein Profil</strong>
            <span>Lokaler Modus</span>
          </div>
        </div>
      </aside>
      <main className="workspace">{children}</main>
      <nav className="mobile-nav" aria-label="Mobile Navigation">
        {navigation.slice(0, 5).map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              className={cn(view === item.id && "mobile-nav-active")}
              onClick={() => onView(item.id)}
            >
              <Icon aria-hidden />
              <span>{item.label.split(" ")[0]}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}

