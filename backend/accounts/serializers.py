from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ApiKey, OnboardingProgress, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("email", "password")

    def validate_email(self, value):
        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        password = attrs["password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        refresh = RefreshToken.for_user(user)

        return {
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "created_at")
        read_only_fields = fields


class OAuthLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "github"])
    # Authorization-code flow only. `email`/`provider_user_id` are never
    # accepted as proof of identity; the fields remain accepted-but-ignored
    # for backward compatibility of the request shape.
    code = serializers.CharField(required=True, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    name = serializers.CharField(required=False, allow_blank=True, default="")
    provider_user_id = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = (
            "id",
            "name",
            "prefix",
            "workspace",
            "scopes",
            "last_used_at",
            "revoked",
            "created_at",
        )
        read_only_fields = (
            "id",
            "prefix",
            "last_used_at",
            "revoked",
            "created_at",
        )


class OnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingProgress
        fields = (
            "step",
            "completed",
            "first_monitor_id",
            "engine",
            "webhook_configured",
            "updated_at",
        )
        read_only_fields = ("updated_at",)
