from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User

admin.site.register(User, UserAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "description"]
    filter_horizontal = ["permissions"]
