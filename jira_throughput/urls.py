from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("forecaster.urls")),
    path("", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
]
