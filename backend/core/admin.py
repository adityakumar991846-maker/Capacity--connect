"""
Django admin configuration for the core app.

Registers UserProfile with the admin site and provides an inline
for the User admin page.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile on the User admin page."""
    model = UserProfile
    can_delete = False
    verbose_name = 'Profile'
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    """Extended User admin with UserProfile inline."""
    inlines = (UserProfileInline,)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Standalone admin view for UserProfile."""
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user',)


# Re-register User with the extended admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
