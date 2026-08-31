from rest_framework.permissions import BasePermission


class HasSpecialStatus(BasePermission):
    """
    Équivalent API de PermissionRequiredMixin + permission_required = "books.special_status"
    utilisée par BookDetailView côté site classique.

    Un superuser passe toujours (Django considère qu'un superuser a toutes
    les permissions), les autres users doivent s'être vu attribuer
    explicitement "special_status" (via l'admin Django ou un groupe).
    """

    message = "Vous n'avez pas la permission de consulter le détail de ce livre."

    def has_permission(self, request, view):
        return request.user.has_perm("books.special_status")