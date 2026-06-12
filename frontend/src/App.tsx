import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { api } from "@/api"
import { AppShell, type View } from "@/components/AppShell"
import { GeneratorCard } from "@/components/GeneratorCard"
import { InsightsPanel } from "@/components/InsightsPanel"
import { PlaylistTable } from "@/components/PlaylistTable"
import { SystemPanel } from "@/components/SystemPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import type { DashboardData, PlaylistRun, Track } from "@/types"

type Profile = { id: string; name: string; is_primary: boolean; preferred_genres: string[] }
type Session = { id: string; started_at: string; ended_at: string; profile_id: string | null; profile_name: string | null; profile_confidence: number | null; assignment_reason: string | null; event_count: number }
type Automation = { enabled: boolean; daily_time: string; duration_minutes: number; discovery_percent: number }

function PageHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <header className="page-header">
      <div><h1>{title}</h1><p>{description}</p></div>
      {action}
    </header>
  )
}

function Overview({ dashboard }: { dashboard?: DashboardData }) {
  return (
    <>
      <PageHeader
        title="Guten Abend!"
        description="Bereit für den passenden Soundtrack?"
        action={
          <div className="connection-state">
            <span className={dashboard?.summary.spotify_connected ? "connection-dot" : "connection-dot connection-off"} />
            <div><strong>{dashboard?.summary.spotify_connected ? "Spotify verbunden" : "Demo-Modus aktiv"}</strong><span>Lokale Daten bleiben lokal</span></div>
          </div>
        }
      />
      <div className="overview-grid">
        <div className="main-column">
          <GeneratorCard />
          <PlaylistTable run={dashboard?.latest_run ?? null} />
        </div>
        <aside className="right-column">
          <InsightsPanel run={dashboard?.latest_run ?? null} />
          <SystemPanel />
        </aside>
      </div>
    </>
  )
}

function RunsView() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.get<PlaylistRun[]>("/api/playlist-runs") })
  const [selected, setSelected] = useState<PlaylistRun | null>(null)
  const active = selected ?? runs.data?.[0] ?? null
  return (
    <>
      <PageHeader title="Playlist-Verlauf" description="Jeder Lauf behält Scores, Gründe und Algorithmusversion." />
      <div className="split-view">
        <Card>
          <CardHeader><CardTitle>Erzeugte Mixes</CardTitle><CardDescription>Die letzten 30 Läufe</CardDescription></CardHeader>
          <CardContent className="run-list">
            {runs.data?.map((run) => (
              <button key={run.id} onClick={() => setSelected(run)}>
                <strong>{run.context}</strong>
                <span>{new Date(run.created_at).toLocaleString("de-DE")} · {run.tracks.length} Titel</span>
              </button>
            ))}
          </CardContent>
        </Card>
        <PlaylistTable run={active} />
      </div>
    </>
  )
}

function SessionsView() {
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api.get<Session[]>("/api/sessions") })
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles") })
  const patch = useMutation({
    mutationFn: ({ sessionId, profileId }: { sessionId: string; profileId: string }) => api.patch(`/api/sessions/${sessionId}/profile`, { profile_id: profileId }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  })
  return (
    <>
      <PageHeader title="Hörverlauf" description="Sessions, geschätzte Gastnutzung und manuelle Profilkorrektur." />
      <Card>
        <CardContent className="table-wrap padded">
          <table className="track-table">
            <thead><tr><th>Beginn</th><th>Titel</th><th>Profil</th><th>Konfidenz</th><th>Grund</th></tr></thead>
            <tbody>
              {sessions.data?.map((session) => (
                <tr key={session.id}>
                  <td>{new Date(session.started_at).toLocaleString("de-DE")}</td>
                  <td>{session.event_count}</td>
                  <td>
                    <select value={session.profile_id ?? ""} onChange={(event) => patch.mutate({ sessionId: session.id, profileId: event.target.value })}>
                      <option value="" disabled>Nicht zugeordnet</option>
                      {profiles.data?.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
                    </select>
                  </td>
                  <td>{session.profile_confidence ? `${Math.round(session.profile_confidence * 100)}%` : "—"}</td>
                  <td>{session.assignment_reason ?? "Noch keine automatische Zuordnung"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </>
  )
}

function ProfilesView() {
  const queryClient = useQueryClient()
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles") })
  const [name, setName] = useState("")
  const create = useMutation({
    mutationFn: () => api.post("/api/profiles", { name, preferred_genres: [] }),
    onSuccess: () => { setName(""); void queryClient.invalidateQueries({ queryKey: ["profiles"] }) },
  })
  return (
    <>
      <PageHeader title="Profile" description="Hauptprofil und erkannte Gastpräferenzen bleiben manuell kontrollierbar." />
      <div className="profile-grid">
        {profiles.data?.map((profile) => (
          <Card key={profile.id}>
            <CardHeader><CardTitle>{profile.name}</CardTitle><CardDescription>{profile.is_primary ? "Hauptprofil" : "Gastprofil"}</CardDescription></CardHeader>
            <CardContent><p className="muted">{profile.preferred_genres.join(", ") || "Noch keine bevorzugten Genres"}</p></CardContent>
          </Card>
        ))}
        <Card>
          <CardHeader><CardTitle>Profil hinzufügen</CardTitle><CardDescription>Für regelmäßige Gäste oder Nutzungskontexte</CardDescription></CardHeader>
          <CardContent className="inline-form"><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Profilname" /><Button disabled={!name || create.isPending} onClick={() => create.mutate()}>Hinzufügen</Button></CardContent>
        </Card>
      </div>
    </>
  )
}

function MusicView() {
  const queryClient = useQueryClient()
  const tracks = useQuery({ queryKey: ["tracks"], queryFn: () => api.get<Track[]>("/api/tracks") })
  const enrich = useMutation({ mutationFn: () => api.post("/api/sync/features"), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tracks"] }) })
  const [selected, setSelected] = useState<Track | null>(null)
  const [bpm, setBpm] = useState("")
  const [key, setKey] = useState("")
  const save = useMutation({
    mutationFn: () => api.patch(`/api/tracks/${selected?.id}/features`, { bpm: bpm ? Number(bpm) : null, musical_key: key || null }),
    onSuccess: () => { setSelected(null); void queryClient.invalidateQueries({ queryKey: ["tracks"] }) },
  })
  const complete = tracks.data?.filter((track) => track.bpm && track.camelot_key).length ?? 0
  const coverage = tracks.data?.length ? complete / tracks.data.length * 100 : 0
  return (
    <>
      <PageHeader title="Musikdaten" description="Nullable Merkmale mit Quelle, Konfidenz und sichtbaren Lücken." action={<Button variant="outline" onClick={() => enrich.mutate()}><RefreshCw data-icon="inline-start" />Merkmale ergänzen</Button>} />
      <Card>
        <CardHeader><CardTitle>Datenabdeckung</CardTitle><CardDescription>{complete} von {tracks.data?.length ?? 0} Tracks besitzen BPM und Camelot-Key.</CardDescription></CardHeader>
        <CardContent><Progress value={coverage} /></CardContent>
      </Card>
      {selected ? (
        <Card>
          <CardHeader><CardTitle>{selected.name} korrigieren</CardTitle><CardDescription>Manuelle Werte erhalten höchste Konfidenz.</CardDescription></CardHeader>
          <CardContent className="inline-form"><Input type="number" placeholder="BPM" value={bpm} onChange={(event) => setBpm(event.target.value)} /><Input placeholder="Tonart, z. B. Am" value={key} onChange={(event) => setKey(event.target.value)} /><Button onClick={() => save.mutate()}>Speichern</Button><Button variant="ghost" onClick={() => setSelected(null)}>Abbrechen</Button></CardContent>
        </Card>
      ) : null}
      <Card>
        <CardContent className="table-wrap padded">
          <table className="track-table">
            <thead><tr><th>Titel</th><th>BPM</th><th>Camelot</th><th>Quelle</th><th>Konfidenz</th><th></th></tr></thead>
            <tbody>
              {tracks.data?.map((track) => (
                <tr key={track.id}><td><strong>{track.name}</strong><span>{track.artists.join(", ")}</span></td><td>{track.bpm ?? "Fehlt"}</td><td>{track.camelot_key ?? "Fehlt"}</td><td><Badge variant="outline">{track.feature_source}</Badge></td><td>{track.feature_confidence ? `${Math.round(track.feature_confidence * 100)}%` : "—"}</td><td><Button size="sm" variant="ghost" onClick={() => { setSelected(track); setBpm(track.bpm?.toString() ?? ""); setKey("") }}>Bearbeiten</Button></td></tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </>
  )
}

function SettingsView() {
  const queryClient = useQueryClient()
  const automation = useQuery({ queryKey: ["automation"], queryFn: () => api.get<Automation>("/api/settings/automation") })
  const [draft, setDraft] = useState<Automation | null>(null)
  const value = draft ?? automation.data
  const save = useMutation({ mutationFn: () => api.patch<Automation>("/api/settings/automation", value), onSuccess: () => { setDraft(null); void queryClient.invalidateQueries({ queryKey: ["automation"] }) } })
  return (
    <>
      <PageHeader title="Einstellungen" description="Komfortoptionen im Dashboard; Zugangsdaten bleiben zentral in der Root-.env." />
      <Card>
        <CardHeader><CardTitle>Tägliche Standardplaylist</CardTitle><CardDescription>Standardmäßig fünf Stunden um 06:00 Europe/Berlin.</CardDescription></CardHeader>
        <CardContent className="settings-form">
          <label><span>Automatisch erstellen</span><input type="checkbox" checked={value?.enabled ?? false} onChange={(event) => setDraft({ ...(value as Automation), enabled: event.target.checked })} /></label>
          <label><span>Uhrzeit</span><Input type="time" value={value?.daily_time ?? "06:00"} onChange={(event) => setDraft({ ...(value as Automation), daily_time: event.target.value })} /></label>
          <label><span>Dauer in Minuten</span><Input type="number" value={value?.duration_minutes ?? 300} onChange={(event) => setDraft({ ...(value as Automation), duration_minutes: Number(event.target.value) })} /></label>
          <label><span>Discovery-Anteil</span><Input type="number" value={value?.discovery_percent ?? 20} onChange={(event) => setDraft({ ...(value as Automation), discovery_percent: Number(event.target.value) })} /></label>
          <Button disabled={!value || save.isPending} onClick={() => save.mutate()}>Einstellungen speichern</Button>
        </CardContent>
      </Card>
    </>
  )
}

export default function App() {
  const [view, setView] = useState<View>("overview")
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<DashboardData>("/api/dashboard") })
  const content = {
    overview: <Overview dashboard={dashboard.data} />,
    generate: <><PageHeader title="Playlist erstellen" description="Kriterien präzisieren und sofort einen kohärenten Mix erzeugen." /><GeneratorCard expanded /><PlaylistTable run={dashboard.data?.latest_run ?? null} /></>,
    history: <SessionsView />,
    profiles: <ProfilesView />,
    music: <MusicView />,
    settings: <SettingsView />,
    system: <><PageHeader title="Systemstatus" description="Keine Tokens, Schlüssel oder personenbezogenen Inhalte werden im Frontend angezeigt." /><SystemPanel detailed /><RunsView /></>,
  }[view]
  return <AppShell view={view} onView={setView}>{content}</AppShell>
}

