from urllib.request import urlopen
import re
from datetime import datetime, timedelta


from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.text import slugify
from django.contrib import messages

from geopy.geocoders import Nominatim
import xmltodict

from .forms import SelectForm


_FORECAST_URL = 'http://api.met.no/weatherapi/locationforecastlts/1.2/?'
_DATE_TIME_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')

def select(request):
    if request.method == "POST":
        form = SelectForm(request.POST)
        if form.is_valid():
            name = request.POST['name']
            if name == '':
                messages.error(request, "Wprowadź nazwę miejscowości!")
                return redirect(reverse('select'))
            slug = slugify(name)
            request.session['name'] = name
            return HttpResponseRedirect(
                reverse('forecast-details', args=(slug, ))
            )
    else:
        form = SelectForm()
    return render(request, "forecast/index.html", {'form':form})

def _coordinates(name):
    geolocator = Nominatim()
    location = geolocator.geocode(name)
    return (location.latitude, location.longitude)

def _get_url(url, lat, lng):
    return url + 'lat=%s;lon=%s' % (lat, lng)


precipitation_3_hours_values = []
precipitation_6_hours_values = []
precipitation_3_hours_data = []
precipitation_6_hours_data = []

def _get_meteo_parameters(time_from, time_to, data):
    temperature = data['location']['temperature']['@value']
    pressure = data['location']['pressure']['@value']
    humidity = data['location']['humidity']['@value']
    cloudiness = data['location']['cloudiness']['@percent']
    return (time_from, time_to, temperature, pressure, humidity, cloudiness)

def _get_precipitation_parameters(time_from, time_to, data):
    if time_to - time_from == timedelta(hours=3):
        precipitation_value = data['location']['precipitation']['@value']
        precipitation_3_hours_values.append(time_from)
        precipitation_3_hours_values.append(float(precipitation_value))
    if time_to - time_from == timedelta(hours=6):
        precipitation_value = data['location']['precipitation']['@value']
        precipitation_6_hours_values.append(time_from)
        precipitation_6_hours_values.append(float(precipitation_value))


def _get_data(url):
    with urlopen(url) as file:
        raw_data = file.read()
    data_xml = xmltodict.parse(raw_data)

    periodic_data = data_xml['weatherdata']['product']['time']
    meteo_parameters = []
    precipitation_parameters = []

    for period in periodic_data:
        time_from_raw = _DATE_TIME_REGEX.match(period['@from']).group()
        time_to_raw = _DATE_TIME_REGEX.match(period['@to']).group()
        time_from = datetime.strptime(time_from_raw, '%Y-%m-%dT%H:%M')
        time_to = datetime.strptime(time_to_raw, '%Y-%m-%dT%H:%M')
        try:
            meteo_parameters.append(_get_meteo_parameters(time_from, time_to, period))
        except KeyError:
            precipitation_parameters.append(_get_precipitation_parameters(time_from,
                                                                          time_to,
                                                                          period))
        except KeyError:
            pass

    return (meteo_parameters, precipitation_parameters)

def forecast_details(request, slug):
    request.session.modified = True
    name = request.session.pop('name')
    try:
        location = _coordinates(name)
    except AttributeError:
        messages.error(request, "Wprowadź poprawną nazwę miasta/miejscowości!")
        return redirect(reverse('select'))
    url = _get_url(_FORECAST_URL, location[0], location[1])
    data = _get_data(url)
    meteo_parameters = _get_data(url)[0]
    precipitation_parameters = _get_data(url)[1]
    context = {
        'name': name,
        'lat': location[0],
        'lng': location[1],
        'url': url,
        'data': meteo_parameters,
        'data1': precipitation_6_hours_values,
        'data2': precipitation_3_hours_values,
    }
    return render(request, "forecast/details.html", context)
