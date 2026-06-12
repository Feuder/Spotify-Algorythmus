from app.models import PlaylistRun, Track


def track_payload(track: Track) -> dict:
    return {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "uri": track.uri,
        "name": track.name,
        "artists": [artist.name for artist in track.artists],
        "album_name": track.album_name,
        "duration_ms": track.duration_ms,
        "image_url": track.image_url,
        "popularity": track.popularity,
        "genres": track.genres,
        "bpm": track.bpm,
        "musical_key": track.musical_key,
        "camelot_key": track.camelot_key,
        "energy": track.energy,
        "feature_source": track.feature_source.value,
        "feature_confidence": track.feature_confidence,
        "features_checked_at": track.features_checked_at,
        "is_saved": track.is_saved,
        "is_discovery": track.is_discovery,
    }


def run_payload(run: PlaylistRun) -> dict:
    return {
        "id": run.id,
        "created_at": run.created_at,
        "context": run.context,
        "requested_duration_minutes": run.requested_duration_minutes,
        "actual_duration_ms": run.actual_duration_ms,
        "requested_discovery_percent": run.requested_discovery_percent,
        "actual_discovery_percent": run.actual_discovery_percent,
        "intent": run.intent,
        "algorithm_version": run.algorithm_version,
        "status": run.status.value,
        "spotify_playlist_id": run.spotify_playlist_id,
        "spotify_playlist_url": run.spotify_playlist_url,
        "tracks": [
            {
                "position": item.position,
                "score": item.score,
                "reasons": item.reasons,
                "score_details": item.score_details,
                "track": track_payload(item.track),
            }
            for item in run.tracks
        ],
    }
