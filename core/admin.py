from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from .models import Restaurant


class RestaurantAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Set a new password for this owner's login. Leave blank to keep existing password."
    )

    class Meta:
        model = Restaurant
        fields = ('name', 'owner_name', 'owner_email', 'owner_phone', 'password')

    def clean_owner_name(self):
        name = self.cleaned_data.get('owner_name', '').strip()
        if not name:
            raise forms.ValidationError("Owner name is required.")
        return name

    def clean(self):
        cleaned = super().clean()
        # On create, password is required
        if not self.instance.pk and not cleaned.get('password'):
            self.add_error('password', 'Password is required when creating a new restaurant.')
        return cleaned


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    form = RestaurantAdminForm
    list_display = ('name', 'owner_name', 'owner_email', 'owner_phone', 'login_username', 'created_at')
    search_fields = ('name', 'owner_name', 'owner_email')
    readonly_fields = ('login_username',)

    fieldsets = (
        ('Restaurant Info', {
            'fields': ('name',)
        }),
        ('Owner Details', {
            'fields': ('owner_name', 'owner_email', 'owner_phone')
        }),
        ('Login Credentials', {
            'fields': ('password',),
            'description': 'Username is auto-generated from Owner Name. Password is set here.'
        }),
        ('Login Info (read-only)', {
            'fields': ('login_username',),
        }),
    )

    def login_username(self, obj):
        if obj.owner_user:
            return obj.owner_user.username
        return '—'
    login_username.short_description = 'Login Username'

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get('password')
        owner_name = obj.owner_name.strip()

        # Build a clean username from owner name
        username = owner_name.lower().replace(' ', '_')
        base_username = username
        counter = 1

        if not change:
            # New restaurant — create a new user
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            user = User.objects.create_user(
                username=username,
                email=obj.owner_email,
                password=password,
                first_name=owner_name,
            )
            obj.owner_user = user
        else:
            # Existing restaurant — update user details
            user = obj.owner_user
            if user:
                # Update username if owner name changed
                new_username = owner_name.lower().replace(' ', '_')
                if user.username != new_username:
                    while User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                        new_username = f"{new_username}_{counter}"
                        counter += 1
                    user.username = new_username
                user.email = obj.owner_email
                user.first_name = owner_name
                if password:
                    user.set_password(password)
                user.save()

        super().save_model(request, obj, form, change)
