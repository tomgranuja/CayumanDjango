from django.contrib.auth.backends import BaseBackend

from cayuman.permissions import custom_permissions


class CayumanPermissionBackend(BaseBackend):
    def has_perm(self, user, perm, obj=None):
        # check custom permission
        if perm in custom_permissions:
            return custom_permissions[perm](user, obj)

        # if not found let's call default
        return super().has_perm(user, perm, obj)
