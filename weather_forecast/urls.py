"""weather_forecast URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Import the include() function: from django.conf.urls import url, include
    3. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import url
from django.contrib import admin
from weather_forecast import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


from weather_forecast.apps.forecast.views import select, forecast_details, places

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', select, name='select'),
    url(r'^(?P<name>[\s\w-]+)/$', places, name='places'),
    url(r'^(?P<name>[\D]+)/(?P<country>[\D]+)/(?P<latitude>-?[0-9]{1,3}\.[0-9]+)-(?P<longitude>-?[0-9]{1,3}\.[0-9]+)/$',
        forecast_details, name='forecast-details'),

]

if settings.DEBUG == True:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
