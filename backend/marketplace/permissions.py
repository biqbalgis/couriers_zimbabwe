from rest_framework.permissions import BasePermission, SAFE_METHODS

def has_role(user, *roles): return bool(user and user.is_authenticated and (user.is_superuser or user.role in roles))
class IsAdmin(BasePermission):
    def has_permission(self,request,view): return has_role(request.user,"admin")
class IsOpsOrFinance(BasePermission):
    def has_permission(self, request, view): return has_role(request.user,"ops","finance","admin")
class IsOps(BasePermission):
    def has_permission(self, request, view): return has_role(request.user,"ops","admin")
class IsSupport(BasePermission):
    def has_permission(self, request, view): return has_role(request.user,"support","ops","admin")
class IsStationOps(BasePermission):
    def has_permission(self, request, view): return has_role(request.user,"station_operator","ops","admin")
class RoleWriteOrReadOnly(BasePermission):
    def has_permission(self, request, view): return request.method in SAFE_METHODS or has_role(request.user,"ops","admin")
