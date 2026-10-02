from django.contrib.auth import authenticate, update_session_auth_hash
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Profile
from .serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer


class AuthRateThrottle(AnonRateThrottle):
    """Stricter throttle for credential endpoints (brute-force protection)."""

    rate = "20/hour"


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data},
                        status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Exchange email + password for an API token (for mobile / external clients)."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        user = authenticate(request, username=request.data.get("email", ""),
                            password=request.data.get("password", ""))
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        update_session_auth_hash(request, request.user)
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Password changed."})


class ThemePreferenceView(APIView):
    """Persist the light/dark preference for logged-in users (guests use localStorage)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        theme = request.data.get("theme")
        if theme not in Profile.Theme.values:
            return Response({"error": {"message": "Invalid theme."}}, status=400)
        Profile.objects.filter(user=request.user).update(theme=theme)
        return Response({"theme": theme})
