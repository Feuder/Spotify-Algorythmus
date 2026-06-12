export type Track = {
  id: string
  name: string
  artists: string[]
  duration_ms: number
  bpm: number | null
  camelot_key: string | null
  energy: number | null
  genres: string[]
  feature_source: string
  feature_confidence: number | null
  is_discovery: boolean
}

export type RunTrack = {
  position: number
  score: number
  reasons: string[]
  score_details: Record<string, number>
  track: Track
}

export type PlaylistRun = {
  id: string
  created_at: string
  context: string
  requested_duration_minutes: number
  actual_duration_ms: number
  actual_discovery_percent: number
  status: string
  spotify_playlist_url: string | null
  tracks: RunTrack[]
}

export type DashboardData = {
  summary: {
    track_count: number
    feature_coverage_percent: number
    session_count: number
    spotify_connected: boolean
    demo_mode: boolean
  }
  latest_run: PlaylistRun | null
  recent_events: Array<{ id: string; played_at: string; estimated_skip: boolean | null; track: Track }>
}

