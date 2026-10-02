from rest_framework import serializers

from .models import StudyMaterial


class StudyMaterialSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True, default=None)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = StudyMaterial
        fields = ["id", "title", "slug", "material_type", "subject", "subject_name", "chapter",
                  "chapter_name", "topic", "summary", "body", "file", "thumbnail",
                  "reading_minutes", "is_featured", "view_count", "is_sample", "is_published",
                  "url"]
        read_only_fields = ["view_count"]
