KEY_TO_CAMELOT = {
    "G#m": "1A",
    "Abm": "1A",
    "B": "1B",
    "Ebm": "2A",
    "D#m": "2A",
    "F#": "2B",
    "Gb": "2B",
    "Bbm": "3A",
    "A#m": "3A",
    "Db": "3B",
    "C#": "3B",
    "Fm": "4A",
    "Ab": "4B",
    "G#": "4B",
    "Cm": "5A",
    "Eb": "5B",
    "D#": "5B",
    "Gm": "6A",
    "Bb": "6B",
    "A#": "6B",
    "Dm": "7A",
    "F": "7B",
    "Am": "8A",
    "C": "8B",
    "Em": "9A",
    "G": "9B",
    "Bm": "10A",
    "D": "10B",
    "F#m": "11A",
    "Gbm": "11A",
    "A": "11B",
    "C#m": "12A",
    "Dbm": "12A",
    "E": "12B",
}


def to_camelot(key: str | None) -> str | None:
    if not key:
        return None
    normalized = key.strip().replace(" minor", "m").replace(" major", "")
    return KEY_TO_CAMELOT.get(normalized)


def camelot_compatibility(first: str | None, second: str | None) -> float:
    if not first or not second:
        return 0.45
    if first == second:
        return 1.0
    try:
        first_num, first_mode = int(first[:-1]), first[-1]
        second_num, second_mode = int(second[:-1]), second[-1]
    except (ValueError, IndexError):
        return 0.3
    if first_num == second_num and first_mode != second_mode:
        return 0.9
    if first_mode == second_mode and ((first_num - second_num) % 12 in {1, 11}):
        return 0.85
    return 0.2
