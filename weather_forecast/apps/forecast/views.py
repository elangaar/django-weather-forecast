from urllib.request import urlopen

from datetime import datetime, timedelta
import re
import os

import logging
logging.basicConfig(level=logging.DEBUG, format="%(message)s")

import dateutil.parser as dparser

from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib import messages
from django.template.loader import render_to_string


from geopy.geocoders import Nominatim
import xmltodict
from PIL import Image
import json
from pytz import timezone

from .forms import SelectForm
from weather_forecast.settings import BASE_DIR, TIME_ZONE


FORECAST_URL = 'http://api.met.no/weatherapi/locationforecastlts/1.2/?'
DATE_TIME_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
PLOT_PATH = os.path.join(BASE_DIR, 'static', 'forecast', 'plots')

def select(request):
    if request.method == "POST":
        form = SelectForm(request.POST)
        if form.is_valid():
            name = request.POST['name']
            if name == '':
                messages.error(request, "Wprowadź nazwę miejscowości!")
                return redirect(reverse('select'))

            return HttpResponseRedirect(
                reverse('places', args=(name, ))
            )
    else:
        form = SelectForm()
    return render(request, "forecast/index.html", {'form':form})

def places(request, name):
    geolocator = Nominatim()
    locations = geolocator.geocode(name, exactly_one=False)
    if locations == None:
        messages.error(request, "Wprowadź nazwę miejscowości!")
        return redirect(reverse('select'))

    country = locations[0].address
    country = country.split(', ')[-1]
    logging.debug(country)
    logging.debug(type(country))
    context = {
        'locations': locations,
        'country': country,
        'name': name,
    }

    return render(request, "forecast/places.html", context)

def _get_url(url, lat, lng):
    return url + 'lat=%s;lon=%s' % (lat, lng)

precipitation_3_hours_parameters = []
precipitation_6_hours_parameters = []

def _get_meteo_parameters(time_from, time_to, data):
    temperature = data['location']['temperature']['@value']
    pressure = data['location']['pressure']['@value']
    humidity = data['location']['humidity']['@value']
    cloudiness = data['location']['cloudiness']['@percent']
    return (time_from, time_to, temperature, pressure, humidity, cloudiness)

def _get_precipitation_parameters(time_from, time_to, data):
    if time_to - time_from == timedelta(hours=3):
        precipitation_value = data['location']['precipitation']['@value']
        time = [time_from.year, time_from.month, time_from.day, time_from.hour,
                time_from.minute]
        precipitation_3_hours_parameters.append([time, float(precipitation_value)])

    if time_to - time_from == timedelta(hours=6):
        precipitation_value = data['location']['precipitation']['@value']
        time = [time_from.year, time_from.month, time_from.day, time_from.hour,
                time_from.minute]
        precipitation_6_hours_parameters.append([time, float(precipitation_value)])

def _get_data(url):
    with urlopen(url) as file:
        raw_data = file.read()
    data_xml = xmltodict.parse(raw_data)

    periodic_data = data_xml['weatherdata']['product']['time']
    meteo_parameters = []

    for period in periodic_data:
        time_from_raw = DATE_TIME_REGEX.match(period['@from']).group()
        time_to_raw = DATE_TIME_REGEX.match(period['@to']).group()
        time_from = datetime.strptime(time_from_raw, '%Y-%m-%dT%H:%M')
        time_to = datetime.strptime(time_to_raw, '%Y-%m-%dT%H:%M')
        try:
            meteo_parameters.append(_get_meteo_parameters(time_from, time_to, period))
        except KeyError:
            _get_precipitation_parameters(time_from, time_to, period)
        except KeyError:
            pass

    return (meteo_parameters)

def get_current_location_time(lat, lng):
    URL = 'https://maps.googleapis.com/maps/api/timezone/json?location=%s,%s&timestamp=1458000000&key='
    timezone_url = URL % (lat, lng)
    timezone_key_url = timezone_url + 'AIzaSyCdQRXIWzZ5NzA8_-IpLMAG8iwR6QUv9T8'
    with urlopen(timezone_url) as url:
        data = url.read().decode('utf-8')
    data_json = json.loads(data)
    location_timezone = data_json['timeZoneId']
    local_timezone = timezone(TIME_ZONE)
    location_time_zone = timezone(location_timezone)
    local_dt = local_timezone.localize(datetime.now())
    location_dt = local_dt.astimezone(location_time_zone)
    fmt = "%H:%M %p"
    fmdt = "%d %B %Y %H:%M"
    location_time_str = datetime.strftime(location_dt, fmt)
    location_datetime_str = datetime.strftime(location_dt, fmdt)
    location_time = datetime.strptime(location_time_str, fmt)
    return (location_dt, location_datetime_str, location_time)

def get_time_of_day(lat, lng):
    URL = 'http://api.sunrise-sunset.org/json'
    url_sunrise_sunset_times = URL + "?lat=%s&lng=%s" % (lat, lng)
    with urlopen(url_sunrise_sunset_times) as url:
        data = url.read().decode('utf-8')
    data_json = json.loads(data)
    sunrise_str = str(data_json['results']['sunrise'])
    sunset_str = str(data_json['results']['sunset'])
    sunrise = dparser.parse(sunrise_str)
    sunset = dparser.parse(sunset_str)

    now = get_current_location_time(lat, lng)[2]
    if sunrise < now < sunset:
        return 'day'
    return 'night'

def current_location_time_display(location_dt):
    import locale
    location_dt = datetime.strptime(location_dt, "%d %B %Y %H:%M")
    locale.setlocale(locale.LC_TIME, "pl_PL.utf8")
    return datetime.strftime(location_dt, "%d %B %Y %H:%M")

def forecast_details(request, name, country, latitude, longitude):
    url = _get_url(FORECAST_URL, latitude, longitude)
    meteo_parameters = _get_data(url)

    current_time = datetime.now()
    current_location_time = get_current_location_time(latitude, longitude)[1]
    current_temperature = meteo_parameters[0][2]
    current_pressure = meteo_parameters[0][3]
    current_humidity = meteo_parameters[0][4]
    current_cloudiness = float(meteo_parameters[0][5])
    current_precipitation = 'opad'

    time_of_day = get_time_of_day(latitude, longitude)

    Lat = str(latitude).replace(',', '.')
    Lng = str(longitude).replace(',', '.')

    current_location_time_display_value = current_location_time_display(current_location_time)

    times = [time[0] for time in meteo_parameters]
    times_tuples = []
    for i in range(len(times)):
        time = times[i]
        time_tuple = ([time.year, time.month, time.day, time.hour, time.minute])
        times_tuples.append(time_tuple)
    temp_values = [float(value[2]) for value in meteo_parameters]
    press_values = [float(value[3]) for value in meteo_parameters]
    hum_values = [float(value[4]) for value in meteo_parameters]

    context = {
        'name': name,
        'country': country,
        'lat': latitude,
        'lng': longitude,
        'Lat': Lat,
        'Lng': Lng,
        'time_of_day': time_of_day,
        'current_time': current_time,
        'current_location_time': current_location_time_display_value,
        'current_temperature': current_temperature,
        'current_pressure': current_pressure,
        'current_humidity': current_humidity,
        'current_cloudiness': current_cloudiness,
        'current_precipitation': current_precipitation,
        'temperature_values': temp_values,
        'times_tuples': times_tuples,
        'pressure_values': press_values,
        'humidity_values': hum_values,
        'precipitation_3_hours_parameters': precipitation_3_hours_parameters,
        'precipitation_6_hours_parameters': precipitation_6_hours_parameters,
    }
    return render(request, "forecast/details.html", context)
