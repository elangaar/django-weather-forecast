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
from django.utils.text import slugify
from django.contrib import messages
from django.template.loader import render_to_string


from geopy.geocoders import Nominatim
import xmltodict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
                reverse('forecast-details', args=(name, ))
            )
    else:
        form = SelectForm()
    return render(request, "forecast/index.html", {'form':form})

def _coordinates(name):
    geolocator = Nominatim()
    location = geolocator.geocode(name)
    country = location[0].split(', ')[-1]
    return (location.latitude, location.longitude, country)

def _get_url(url, lat, lng):
    return url + 'lat=%s;lon=%s' % (lat, lng)


precipitation_3_hours_values = []
precipitation_3_hours_times = []

precipitation_6_hours_values = []
precipitation_6_hours_times = []

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
        logging.debug('time: %s' % time)
        precipitation_3_hours_times.append(time)
        precipitation_3_hours_values.append(float(precipitation_value))

    if time_to - time_from == timedelta(hours=6):
        precipitation_value = data['location']['precipitation']['@value']
        time = [time_from.year, time_from.month, time_from.day, time_from.hour,
                time_from.minute]
        precipitation_6_hours_times.append(time)
        precipitation_6_hours_values.append(float(precipitation_value))


precip_3_values = []
precip_6_values = []

times_tuple_6 = []
def _get_precipitation_values(time_from, time_to, data):
    if time_to - time_from == timedelta(hours=3):
        precipitation_value = data['location']['precipitation']['@value']
        time_tuple_6 = (time_from.year, time_from.month, time_from.day,
                time_from.hour, time_from.minute)
        times_tuple_6.append(time_tuple_6)
        precip_6_values.append((time_tuple_6, float(precipitation_value)))
    if time_to - time_from == timedelta(hours=6):
        precipitation_value = data['location']['precipitation']['@value']
        time_tuple_3 = ([time_from.year, time_from.month, time_from.day,
                time_from.hour, time_from.minute])
        precip_3_values.append((time_tuple_3, float(precipitation_value)))




def _get_data(url):
    with urlopen(url) as file:
        raw_data = file.read()
    data_xml = xmltodict.parse(raw_data)

    periodic_data = data_xml['weatherdata']['product']['time']
    meteo_parameters = []
    precipitation_parameters = []

    for period in periodic_data:
        time_from_raw = DATE_TIME_REGEX.match(period['@from']).group()
        time_to_raw = DATE_TIME_REGEX.match(period['@to']).group()
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
    logging.debug('sunrise_str: %s' % (sunrise_str))
    sunrise = dparser.parse(sunrise_str)
    sunset = dparser.parse(sunset_str)

    # sunrise = datetime.strptime(sunrise, "%H:%M:%S")
    # sunset = datetime.strptime(sunset, "%H:%M:%S")
    
    logging.debug('sunrise: %s, sunset: %s' % (sunrise, sunset))

    now = get_current_location_time(lat, lng)[2]
    if sunrise < now < sunset:
        return 'day'
    return 'night'

def current_location_time_display(location_dt):
    import locale
    location_dt = datetime.strptime(location_dt, "%d %B %Y %H:%M")
    locale.setlocale(locale.LC_TIME, "pl_PL.utf8")
    return datetime.strftime(location_dt, "%d %B %Y %H:%M")

def forecast_details(request, name):
    try:
        location = _coordinates(name)
    except (AttributeError, TypeError):
        messages.error(request, "Wprowadź poprawną nazwę miasta/miejscowości!")
        return redirect(reverse('select'))

    lat, lng, country = location

    url = _get_url(FORECAST_URL, lat, lng)
    meteo_parameters, precipitation_parameters = _get_data(url)

    current_time = datetime.now()
    current_location_time = get_current_location_time(lat, lng)[1]
    current_temperature = meteo_parameters[0][2]
    current_pressure = meteo_parameters[0][3]
    current_humidity = meteo_parameters[0][4]
    # current_precipitation = float(precipitation_6_hours_values[0][1])
    current_cloudiness = float(meteo_parameters[0][5])

    time_of_day = get_time_of_day(lat, lng)

    Lat = str(lat).replace(',', '.')
    Lng = str(lng).replace(',', '.')
    pora = 'noc'

    current_location_time_display_value = current_location_time_display(current_location_time)

    logging.debug('precipitation_3_hours_values: %s' % precipitation_3_hours_values)

    # precip_6_times = []
    # for i in range(len(precipitation_6_hours_values)):
    #     time = ([precipitation_6_hours_values[i][0].year,
    #             precipitation_6_hours_values[i][0].month,
    #             precipitation_6_hours_values[i][0].day,
    #             precipitation_6_hours_values[i][0].hour,
    #             precipitation_6_hours_values[i][0].minute])
    #     precip_6_times.append(time)

    # precip_6_values = []
    # for i in range(len(precipitation_6_hours_values)):
    #     value = precipitation_6_hours_values[i][1]
    #     precip_6_values.append(value)

    # precip_3_times = []
    # for i in range(len(precipitation_3_hours_values)):
    #     time = ([precipitation_3_hours_values[i][0].year,
    #             precipitation_3_hours_values[i][0].month,
    #             precipitation_3_hours_values[i][0].day,
    #             precipitation_3_hours_values[i][0].hour,
    #             precipitation_3_hours_values[i][0].minute])
    #     precip_3_times.append(time)

    # precip_3_values = []
    # for i in range(len(precipitation_3_hours_values)):
    #     value = precipitation_3_hours_values[i][1]
    #     precip_3_values.append(value)


    times = [time[0] for time in meteo_parameters]
    len_times = len(times)
    times_tuples = []
    for i in range(len_times):
        time = times[i]
        time_tuple = ([time.month, time.day, time.year, time.hour, time.minute])
        times_tuples.append(time_tuple)
    temp_values = [float(value[2]) for value in meteo_parameters]
    press_values = [float(value[3]) for value in meteo_parameters]
    hum_values = [float(value[4]) for value in meteo_parameters]
    # prec_6_values = [float(value[1]) for value in precipitation_6_hours_values]
    # prec_3_values = [value[1] for value in precipitation_3_hours_values]

    logging.debug(precipitation_3_hours_times)
    context = {
        'name': name,
        'lat': lat,
        'lng': lng,
        'Lat': Lat,
        'Lng': Lng,
        'time_of_day': time_of_day,
        'country': country,
        'current_time': current_time,
        'current_location_time': current_location_time_display_value,
        'current_temperature': current_temperature,
        'current_pressure': current_pressure,
        'current_humidity': current_humidity,
        # 'current_precipitation': current_precipitation,
        'current_cloudiness': current_cloudiness,
        'url': url,
        'data': meteo_parameters,
        'data1': precipitation_6_hours_values,
        'precipitation_3_hours_values': precipitation_3_hours_values,
        'precipitation_3_hours_times': precipitation_3_hours_times,
        'precipitation_6_hours_values': precipitation_6_hours_values,
        'precipitation_6_hours_times': precipitation_6_hours_times,
        'len_times': len_times,
        'temperature_values': temp_values,
        'times_tuples': times_tuples,
        'pressure_values': press_values,
        'humidity_values': hum_values,
        # 'precipitation_6_hours_values': prec_6_values,
        # 'precipitation_3_hours_values': prec_3_values,
        # 'precipitation_3_hours_times': prec_3_times,
        'times_tuple_6': times_tuple_6,
        'precipitation_parameters': precipitation_parameters,
        # 'precip_6_times': precip_6_times,
        # 'precip_3_times': precip_3_times,
    }
    return render(request, "forecast/details.html", context)
