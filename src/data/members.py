def normalize_telegram_handle(handle_value):
    cleaned_value = str(handle_value or "").strip()
    if not cleaned_value:
        return ""
    if cleaned_value.startswith("@"):
        return cleaned_value
    return f"@{cleaned_value}"


def build_member_identity_key(member):
    if member["telegram"]:
        return member["telegram"].lower()
    return member["name"].lower()


def build_member_alias_set(member):
    aliases = {member["name"].lower()}
    if member["telegram"]:
        aliases.add(member["telegram"].lower())
    return aliases


def normalize_member(item):
    if not isinstance(item, dict):
        raise ValueError("each member must be an object")

    name_value = str(item.get("name", "")).strip()
    telegram_value = normalize_telegram_handle(item.get("telegram"))

    if not name_value:
        raise ValueError("each member requires a name")

    member = {"name": name_value, "telegram": telegram_value}
    member["key"] = build_member_identity_key(member)
    member["aliases"] = build_member_alias_set(member)
    return member
