from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

from boards.models import Board, ClassLevel, Subject

from .models import Profile

User = get_user_model()


class StyledFormMixin:
    """Adds Bootstrap classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label="Email", widget=forms.EmailInput(
        attrs={"autofocus": True, "autocomplete": "email", "placeholder": "you@example.com"}))
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput(
        attrs={"autocomplete": "current-password", "placeholder": "Your password"}))


class SignUpForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150, label="First name",
                                 widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=150, label="Last name", required=False,
                                widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    board = forms.ModelChoiceField(queryset=Board.objects.published(), required=False,
                                   empty_label="Select your board (optional)")
    class_level = forms.ModelChoiceField(queryset=ClassLevel.objects.published(), required=False,
                                         label="Class", empty_label="Select your class (optional)")
    password1 = forms.CharField(label="Password", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text="At least 8 characters; not entirely numeric.")
    password2 = forms.CharField(label="Confirm password", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_level"].widget.attrs.update({
            "data-depends-on": "id_board", "data-source": "/api/v1/classes/?board=",
        })

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. "
                                        "Try signing in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        board, class_level = cleaned.get("board"), cleaned.get("class_level")
        if class_level and board and class_level.board_id != board.id:
            self.add_error("class_level", "This class doesn't belong to the selected board.")
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords don't match.")
        if p1:
            candidate = User(email=cleaned.get("email", ""), first_name=cleaned.get("first_name", ""))
            try:
                password_validation.validate_password(p1, candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(email=data["email"], password=data["password1"],
                                        first_name=data["first_name"],
                                        last_name=data.get("last_name", ""))
        profile = user.profile
        profile.board = data.get("board") or (data["class_level"].board if data.get("class_level") else None)
        profile.class_level = data.get("class_level")
        profile.save()
        return user


class UserNameForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["board", "class_level", "subjects", "school", "phone", "avatar", "exam_date"]
        widgets = {
            "exam_date": forms.DateInput(attrs={"type": "date"}),
            "subjects": forms.SelectMultiple(attrs={"size": 6}),
        }
        labels = {"class_level": "Class"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["board"].queryset = Board.objects.published()
        board_id = self.data.get("board") or getattr(self.instance, "board_id", None)
        class_id = self.data.get("class_level") or getattr(self.instance, "class_level_id", None)
        self.fields["class_level"].queryset = (ClassLevel.objects.published().filter(board_id=board_id)
                                               if board_id else ClassLevel.objects.none())
        self.fields["subjects"].queryset = (Subject.objects.published().filter(class_level_id=class_id)
                                            if class_id else Subject.objects.none())
        self.fields["class_level"].widget.attrs.update(
            {"data-depends-on": "id_board", "data-source": "/api/v1/classes/?board="})
        self.fields["subjects"].widget.attrs.update(
            {"data-depends-on": "id_class_level", "data-source": "/api/v1/subjects/?class_level="})
        self.fields["subjects"].help_text = "Hold Ctrl (or ⌘) to select several subjects."

    def clean(self):
        cleaned = super().clean()
        board, class_level = cleaned.get("board"), cleaned.get("class_level")
        if class_level and board and class_level.board_id != board.id:
            self.add_error("class_level", "This class doesn't belong to the selected board.")
        return cleaned


class PreferencesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["preferred_language", "theme", "explanation_style", "daily_goal_minutes",
                  "email_notifications"]
        labels = {"email_notifications": "Email me about new papers, tests and results"}
