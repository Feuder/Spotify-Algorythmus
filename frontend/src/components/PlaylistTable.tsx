import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ExternalLink, ListPlus } from "lucide-react"
import { api } from "@/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PlaylistRun } from "@/types"

function minutes(milliseconds: number) {
  return Math.round(milliseconds / 60_000)
}

export function PlaylistTable({ run }: { run: PlaylistRun | null }) {
  const queryClient = useQueryClient()
  const publish = useMutation({
    mutationFn: () => api.post<PlaylistRun>(`/api/playlist-runs/${run?.id}/publish`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  })
  const enqueue = useMutation({
    mutationFn: () => api.post<{ enqueued: number }>(`/api/playlist-runs/${run?.id}/enqueue`),
  })
  if (!run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Noch keine Playlist</CardTitle>
          <CardDescription>Erzeuge oben deinen ersten persönlichen Mix.</CardDescription>
        </CardHeader>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader className="playlist-header">
        <div>
          <CardTitle>Zuletzt erzeugte Playlist</CardTitle>
          <CardDescription>
            {minutes(run.actual_duration_ms)} Min. · {run.tracks.length} Titel · Discovery {Math.round(run.actual_discovery_percent)}% · {run.context}
          </CardDescription>
        </div>
        <div className="header-actions">
          <Button variant="outline" onClick={() => publish.mutate()} disabled={publish.isPending}>
            <ExternalLink data-icon="inline-start" aria-hidden />
            Auf Spotify veröffentlichen
          </Button>
          <Button onClick={() => enqueue.mutate()} disabled={enqueue.isPending}>
            <ListPlus data-icon="inline-start" aria-hidden />
            Zur Warteschlange
          </Button>
        </div>
      </CardHeader>
      <CardContent className="table-wrap">
        {(publish.error || enqueue.error) ? <p className="form-message">{(publish.error || enqueue.error)?.message}</p> : null}
        <table className="track-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Titel</th>
              <th>BPM</th>
              <th>Camelot</th>
              <th>Quelle</th>
              <th>Grund</th>
            </tr>
          </thead>
          <tbody>
            {run.tracks.map((item) => (
              <tr key={`${run.id}-${item.position}`}>
                <td>{item.position}</td>
                <td>
                  <strong>{item.track.name}</strong>
                  <span>{item.track.artists.join(", ")}</span>
                </td>
                <td>{item.track.bpm ? Math.round(item.track.bpm) : "—"}</td>
                <td>{item.track.camelot_key ?? "—"}</td>
                <td>
                  <Badge variant={item.track.is_discovery ? "warning" : "success"}>
                    {item.track.is_discovery ? "Neu" : "Bekannt"}
                  </Badge>
                </td>
                <td title={item.reasons.join(" · ")}>{item.reasons[0]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

