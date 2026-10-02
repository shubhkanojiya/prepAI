from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["board", "class_level", "subjects", "avatar", "phone", "school",
                  "preferred_language", "theme", "explanation_style", "daily_goal_minutes",
                  "exam_date", "email_notifications"]

    def validate(self, attrs):
        board = attrs.get("board", getattr(self.instance, "board", None))
        class_level = attrs.get("class_level", getattr(self.instance, "class_level", None))
        if class_level and board and class_level.board_id != board.id:
            raise serializers.ValidationError({"class_level": "Class does not belong to this board."})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined", "profile"]
        read_only_fields = ["id", "email", "date_joined"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        instance = super().update(instance, validated_data)
        if profile_data:
            subjects = profile_data.pop("subjects", None)
            for key, value in profile_data.items():
                setattr(instance.profile, key, value)
            instance.profile.save()
            if subjects is not None:
                instance.profile.subjects.set(subjects)
        return instance


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        candidate = User(email=attrs["email"], first_name=attrs["first_name"])
        password_validation.validate_password(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": "Current password is incorrect."})
        password_validation.validate_password(attrs["new_password"], user)
        return attrs
