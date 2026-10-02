from django.contrib import admin

from core.admin_mixins import PublishableAdminMixin

from .models import Board, Chapter, ClassLevel, Subject, Topic


class ClassLevelInline(admin.TabularInline):
    model = ClassLevel
    extra = 0
    fields = ["name", "number", "slug", "order", "is_published"]
    prepopulated_fields = {"slug": ["name"]}
    show_change_link = True


class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 0
    fields = ["name", "slug", "code", "icon", "color", "is_popular", "order", "is_published"]
    prepopulated_fields = {"slug": ["name"]}
    show_change_link = True


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ["number", "name", "slug", "order", "is_published"]
    prepopulated_fields = {"slug": ["name"]}
    show_change_link = True


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0
    fields = ["name", "slug", "order", "is_published"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Board)
class BoardAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["name", "short_name", "board_type", "state", "is_featured", "order",
                    "is_published"]
    list_editable = ["is_featured", "order", "is_published"]
    list_filter = ["board_type", "is_featured", "is_published"]
    search_fields = ["name", "short_name", "state"]
    prepopulated_fields = {"slug": ["short_name"]}
    inlines = [ClassLevelInline]


@admin.register(ClassLevel)
class ClassLevelAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["name", "board", "number", "order", "is_published"]
    list_filter = ["board", "is_published"]
    search_fields = ["name", "board__name", "board__short_name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["board"]
    inlines = [SubjectInline]


@admin.register(Subject)
class SubjectAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["name", "class_level", "code", "is_popular", "order", "is_published"]
    list_editable = ["is_popular", "order"]
    list_filter = ["class_level__board", "class_level", "is_popular", "is_published"]
    search_fields = ["name", "code", "class_level__name", "class_level__board__short_name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["class_level"]
    list_select_related = ["class_level__board"]
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["name", "subject", "number", "order", "is_published"]
    list_filter = ["subject__class_level__board", "subject__class_level", "is_published"]
    search_fields = ["name", "subject__name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["subject"]
    list_select_related = ["subject__class_level__board"]
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ["name", "chapter", "order", "is_published"]
    list_filter = ["chapter__subject__class_level__board", "is_published"]
    search_fields = ["name", "chapter__name"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["chapter"]
    list_select_related = ["chapter__subject"]
