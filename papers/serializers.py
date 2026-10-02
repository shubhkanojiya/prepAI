from rest_framework import serializers

from .models import QuestionPaper


class QuestionPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_name = serializers.CharField(source="subject.class_level.name", read_only=True)
    board_name = serializers.CharField(source="subject.class_level.board.short_name", read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = QuestionPaper
        fields = ["id", "title", "slug", "subject", "subject_name", "class_name", "board_name",
                  "chapter", "paper_type", "exam_type", "year", "difficulty", "description",
                  "pdf", "solution_pdf", "total_marks", "duration_minutes", "file_size",
                  "view_count", "download_count", "is_sample", "is_published", "url"]
        read_only_fields = ["file_size", "view_count", "download_count"]
