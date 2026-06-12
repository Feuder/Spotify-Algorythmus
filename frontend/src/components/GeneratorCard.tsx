import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Clock3, Sparkles } from "lucide-react"
import { api } from "@/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { PlaylistRun } from "@/types"

export function GeneratorCard({ expanded = false }: { expanded?: boolean }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState("Ein fokussierter Mix für den Nachmittag, melodisch und mit etwas Neuem.")
  const [context, setContext] = useState("fokus")
  const [duration, setDuration] = useState(90)
  const [discovery, setDiscovery] = useState(25)
  const [message, setMessage] = useState("")

  const generate = useMutation({
    mutationFn: async () => {
      const parsed = await api.post<{ intent: Record<string, unknown>; parser: string }>("/api/intents/parse", { text })
      return api.post<PlaylistRun>("/api/playlists/generate", {
        ...parsed.intent,
        context,
        duration_minutes: duration,
        discovery_percent: discovery,
        text,
      })
    },
    onSuccess: (run) => {
      setMessage(`${run.tracks.length} Titel wurden nachvollziehbar zusammengestellt.`)
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      void queryClient.invalidateQueries({ queryKey: ["runs"] })
    },
    onError: (error) => setMessage(error.message),
  })

  return (
    <Card className={expanded ? "generator-expanded" : undefined}>
      <CardHeader>
        <CardTitle>Playlist erzeugen</CardTitle>
        <CardDescription>Beschreibe den Soundtrack. Die Kriterien werden lokal validiert.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="generator-form"
          onSubmit={(event) => {
            event.preventDefault()
            generate.mutate()
          }}
        >
          <label className="field field-wide">
            <span>Deine Beschreibung</span>
            <Textarea value={text} onChange={(event) => setText(event.target.value)} />
            <small>{text.length}/2000 Zeichen</small>
          </label>
          <label className="field">
            <span>Kontext</span>
            <select value={context} onChange={(event) => setContext(event.target.value)}>
              <option value="mix">Ausgewogener Mix</option>
              <option value="fokus">Fokus</option>
              <option value="sport">Sport</option>
              <option value="abend">Entspannen</option>
              <option value="party">Party</option>
            </select>
          </label>
          <label className="field">
            <span>Dauer in Minuten</span>
            <div className="input-with-icon">
              <Clock3 aria-hidden />
              <Input
                type="number"
                min={15}
                max={600}
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
              />
            </div>
          </label>
          <label className="field">
            <span>Discovery: {discovery}%</span>
            <input
              className="range"
              type="range"
              min={0}
              max={100}
              value={discovery}
              onChange={(event) => setDiscovery(Number(event.target.value))}
            />
          </label>
          <Button type="submit" disabled={generate.isPending} className="generate-button">
            <Sparkles data-icon="inline-start" aria-hidden />
            {generate.isPending ? "Wird erzeugt ..." : "Playlist erzeugen"}
          </Button>
        </form>
        {message ? <p className="form-message">{message}</p> : null}
      </CardContent>
    </Card>
  )
}

