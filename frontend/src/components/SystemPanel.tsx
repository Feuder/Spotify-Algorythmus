import { useQuery } from "@tanstack/react-query"
import { CheckCircle2, CircleDashed } from "lucide-react"
import { api } from "@/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

type Status = {
  services: Record<string, { configured?: boolean; connected?: boolean; status?: string; privacy?: string }>
  counts: Record<string, number>
}

const sourceCredits: Record<string, { href: string; label: string }> = {
  getsongbpm: {
    href: "https://getsongbpm.com",
    label: "Musikdaten von GetSongBPM",
  },
}

export function SystemPanel({ detailed = false }: { detailed?: boolean }) {
  const status = useQuery({ queryKey: ["system"], queryFn: () => api.get<Status>("/api/system/status") })
  return (
    <Card>
      <CardHeader>
        <CardTitle>System & Datenquellen</CardTitle>
        <CardDescription>{detailed ? "Konfiguration und lokale Datenbestände" : "Aktueller Bereitschaftsstatus"}</CardDescription>
      </CardHeader>
      <CardContent className="status-list">
        {Object.entries(status.data?.services ?? {}).map(([name, service]) => {
          const active = service.status === "ok" || service.connected || service.configured
          return (
            <div className="status-row" key={name}>
              {active ? <CheckCircle2 aria-hidden /> : <CircleDashed aria-hidden />}
              <div>
                <strong>{name}</strong>
                <span>{service.privacy ?? (active ? "Bereit" : "Nicht konfiguriert")}</span>
                {sourceCredits[name] ? (
                  <a href={sourceCredits[name].href} target="_blank" rel="noreferrer">
                    {sourceCredits[name].label}
                  </a>
                ) : null}
              </div>
              <span className={active ? "status-active" : "status-muted"}>{active ? "Aktiv" : "Offen"}</span>
            </div>
          )
        })}
        {detailed ? (
          <div className="count-grid">
            {Object.entries(status.data?.counts ?? {}).map(([name, count]) => (
              <div key={name}><strong>{count}</strong><span>{name}</span></div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
