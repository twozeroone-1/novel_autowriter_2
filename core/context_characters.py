def normalize_character(raw_char: object) -> dict | None:
    if not isinstance(raw_char, dict):
        return None

    required_string_fields = ("id", "name", "role", "description")
    normalized: dict[str, object] = {}
    for field in required_string_fields:
        value = raw_char.get(field)
        if value is None:
            return None
        text = value if isinstance(value, str) else str(value)
        if not text.strip():
            return None
        normalized[field] = text

    traits = raw_char.get("traits")
    if not isinstance(traits, list):
        return None
    normalized_traits: list[str] = []
    for item in traits:
        if item is None:
            continue
        text = item if isinstance(item, str) else str(item)
        if text.strip():
            normalized_traits.append(text)
    normalized["traits"] = normalized_traits
    return normalized


def normalize_characters(chars: list | dict) -> list[dict]:
    if not isinstance(chars, list):
        return []

    normalized: list[dict] = []
    for index, raw_char in enumerate(chars):
        normalized_char = normalize_character(raw_char)
        if normalized_char is None:
            print(f"[ContextManager] Skipping invalid character at index {index}")
            continue
        normalized.append(normalized_char)
    return normalized
