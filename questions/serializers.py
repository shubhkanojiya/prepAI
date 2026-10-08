from rest_framework import serializers

from .models import Question, QuestionOption


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text", "is_correct", "order"]


class QuestionSerializer(serializers.ModelSerializer):
    """Question-bank view (answers visible — this is for practice, not tests)."""

    options = QuestionOptionSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True, default=None)
    topic_name = serializers.CharField(source="topic.name", read_only=True, default=None)
    concepts = serializers.StringRelatedField(many=True, read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Question
        fields = ["id", "subject", "subject_name", "chapter", "chapter_name", "topic",
                  "topic_name", "question_type", "text", "image", "answer", "explanation",
                  "difficulty", "marks", "negative_marks", "concepts", "options", "source",
                  "is_important", "is_published", "url"]

    def _locked_ids(self):
        # Computed once per response; list serializers share this context dict with each row.
        if "locked_question_ids" not in self.context:
            from testengine.services import locked_question_ids

            request = self.context.get("request")
            self.context["locked_question_ids"] = (locked_question_ids(request.user)
                                                   if request else set())
        return self.context["locked_question_ids"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["answers_hidden"] = instance.pk in self._locked_ids()
        if data["answers_hidden"]:  # part of a test this user is taking right now
            data["answer"] = data["explanation"] = ""
            for option in data["options"]:
                option["is_correct"] = None
        return data


class PredictRequestSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000, trim_whitespace=True)
    board = serializers.IntegerField(required=False, allow_null=True)
    class_level = serializers.IntegerField(required=False, allow_null=True)
    subject = serializers.IntegerField(required=False, allow_null=True)


def prediction_payload(report):
    """JSON form of questions.services.predictor.predict()."""
    return {
        "query": report["query"],
        "upcoming_exam_year": report["upcoming_year"],
        "has_matches": report["has_matches"],
        "times_appeared": report["times_appeared"],
        "years": report["years"],
        "stored_paper_years": report["available_years"],
        "appearances": [
            {"year": a["year"], "question_numbers": a["question_numbers"],
             "papers": [{"title": p.title, "url": p.get_absolute_url()} for p in a["papers"]]}
            for a in report["appearances"]
        ],
        "pattern": report["pattern"],
        "likelihood": report["likelihood"],
        "matches": [
            {"id": m["question"].id, "text": m["question"].text, "type": m["type"],
             "similarity_percent": m["percent"], "url": m["question"].get_absolute_url()}
            for m in report["matches"]
        ],
        "related": [
            {"id": r["question"].id, "text": r["question"].text, "similarity_percent": r["percent"],
             "url": r["question"].get_absolute_url()}
            for r in report["related"]
        ],
        "concepts": [{"name": c["concept"].name, "years": c["years"]} for c in report["concepts"]],
        "contains_sample_data": report["contains_sample_data"],
        "disclaimer": report["disclaimer"],
    }


class FrequencySerializer(serializers.Serializer):
    """Serializes questions.services.frequency.analyze_question output."""

    def to_representation(self, analysis):
        return {
            "has_data": analysis["has_data"],
            "frequency": analysis["frequency"],
            "years": analysis["years"],
            "first_year": analysis["first_year"],
            "last_year": analysis["last_year"],
            "pattern": analysis["pattern"],
            "priority": analysis["priority"],
            "appearances": [
                {"year": a["year"], "paper": a["paper"].title,
                 "paper_url": a["paper"].get_absolute_url(),
                 "question_number": a["question_number"],
                 "marks": str(a["marks"]) if a["marks"] is not None else None}
                for a in analysis["appearances"]
            ],
            "related_concepts": [
                {"name": r["concept"].name, "years": r["years"], "count": r["count"]}
                for r in analysis["related_concepts"]
            ],
            "similar_questions": [
                {"id": q.id, "text": q.text[:200], "url": q.get_absolute_url()}
                for q in analysis["similar_questions"]
            ],
            "contains_sample_data": analysis["contains_sample_data"],
            "disclaimer": analysis["disclaimer"],
        }
