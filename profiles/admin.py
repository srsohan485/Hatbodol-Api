from django.contrib import admin
from .models import Profile, UserSettings, PhoneChangeRequest

admin.site.register(Profile)
admin.site.register(UserSettings)
admin.site.register(PhoneChangeRequest)