from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    autocomplete_fields = ["board", "class_level", "subjects"]
    fk_name = "user"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active", "profile__board"]
    search_fields = ["email", "first_name", "last_name", "username"]
    ordering = ["-date_joined"]
    inlines = [ProfileInline]
    fieldsets = BaseUserAdmin.fieldsets
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "username", "first_name", "password1", "password2")}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "board", "class_level", "preferred_language", "theme"]
    list_filter = ["board", "preferred_language", "theme"]
    search_fields = ["user__email", "school"]
    autocomplete_fields = ["user", "board", "class_level", "subjects"]
