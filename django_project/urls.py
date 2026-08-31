"""
URL configuration for django_project project.
...
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import ChangePasswordView, EmailTokenObtainPairView, LogoutView, MeView, RegisterView
urlpatterns = [
    path('anything-but-admin/', admin.site.urls), # hardening the django admin
    path('',include('pages.urls')),
    # Adding the updated modern built-in auth app
    path('accounts/',include('allauth.urls')),
    #path('accounts/',include('accounts.urls')),
    path('books/',include('books.urls')),
    path('reservation/',include('Reservation.urls')),
    # --- API pour le frontend React ---
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register/', RegisterView.as_view(), name='api_register'),
    path('api/me/', MeView.as_view(), name='api_me'),
    path('api/logout/', LogoutView.as_view(), name='api_logout'),
    path('api/change-password/', ChangePasswordView.as_view(), name='api_change_password'),
    path('api/reservation/', include('Reservation.api_urls')),
    path('api/books/', include('books.api_urls')),
    path('api/alerts/', include('alerts.api_urls')),

] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns