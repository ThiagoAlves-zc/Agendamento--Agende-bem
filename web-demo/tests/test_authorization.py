import pytest

from authorization import AccessDenied, Actor, Permission, Role, allowed, require


@pytest.mark.parametrize("role, permission, expected", [
    (Role.ADMIN, Permission.MANAGE_TEMPLATES, True),
    (Role.RECEPTION, Permission.CONFIRM_FIT_IN, True),
    (Role.RECEPTION, Permission.MANAGE_TEMPLATES, False),
    (Role.READ, Permission.VIEW_AGENDA, True),
    (Role.READ, Permission.MANAGE_AGENDA, False),
])
def test_rbac_matrix(role, permission, expected):
    actor = Actor("00000000-0000-0000-0000-000000000001", "user@example.test", role)
    assert allowed(actor, permission) is expected


def test_permission_is_checked_on_server_boundary():
    actor = Actor("00000000-0000-0000-0000-000000000002", "read@example.test", Role.READ)
    with pytest.raises(AccessDenied):
        require(actor, Permission.UPLOAD_FILES)
