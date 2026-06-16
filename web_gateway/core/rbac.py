ROLE_PERMISSIONS = {
    "admin": {
        "users": ["create", "read", "update", "delete", "assign_role"],
        "patients": ["*"],
        "analyses": ["*"],
        "reports": ["*"],
        "settings": ["*"],
        "audit": ["read", "export"],
        "system": ["backup", "restore", "maintenance"],
    },
    "orthodontist": {
        "users": ["read_own"],
        "patients": ["create", "read", "update", "delete_own", "assign"],
        "analyses": ["create", "read", "update", "delete_own", "validate", "review"],
        "reports": ["create", "read", "update", "sign", "send"],
        "tasks": ["create", "read", "update", "assign"],
        "audit": ["read_own"],
    },
    "assistant": {
        "patients": ["create", "read", "update"],
        "analyses": ["read"],
        "reports": ["read"],
        "tasks": ["read", "update_status"],
    },
    "intern": {
        "patients": ["read"],
        "analyses": ["read"],
        "reports": ["read"],
    },
}


def has_permission(role_name: str, resource: str, action: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role_name, {})
    if "*" in perms.get(resource, []):
        return True
    return action in perms.get(resource, [])
