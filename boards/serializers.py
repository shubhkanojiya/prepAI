from rest_framework import serializers

from .models import Board, Chapter, ClassLevel, Subject, Topic


class BoardSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Board
        fields = ["id", "name", "short_name", "slug", "board_type", "state", "description",
                  "logo", "website", "is_featured", "order", "is_published", "url"]


class ClassLevelSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="get_absolute_url", read_only=True)
    board_name = serializers.CharField(source="board.short_name", read_only=True)

    class Meta:
        model = ClassLevel
        fields = ["id", "board", "board_name", "name", "number", "slug", "description", "order",
                  "is_published", "url"]


class SubjectSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="get_absolute_url", read_only=True)
    class_name = serializers.CharField(source="class_level.name", read_only=True)
    board = serializers.IntegerField(source="class_level.board_id", read_only=True)

    class Meta:
        model = Subject
        fields = ["id", "class_level", "class_name", "board", "name", "slug", "code",
                  "description", "icon", "color", "is_popular", "order", "is_published", "url"]


class ChapterSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="get_absolute_url", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Chapter
        fields = ["id", "subject", "subject_name", "name", "slug", "number", "description",
                  "order", "is_published", "url"]


class TopicSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Topic
        fields = ["id", "chapter", "name", "slug", "description", "order", "is_published", "url"]
