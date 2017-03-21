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
        precipitation_record = (time_from, float(precipitation_value))
        precipitation_3_hours_values.append(precipitation_record)
    if time_to - time_from == timedelta(hours=6):
        precipitation_value = data['location']['precipitation']['@value']
        precipitation_record = (time_from, float(precipitation_value))
        precipitation_6_hours_values.append(precipitation_record)


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

def _create_plots(meteo_values, precipitation_3_hours_values,
                  precipitation_6_hours_values):
    fig = plt.figure()
    fig.set_figheight(10)
    fig.subplots_adjust(hspace=0.5)
    matplotlib.rcParams.update({'font.size': 10})
    _create_temperature_plot(meteo_values)
    _create_pressure_plot(meteo_values)
    _create_humidity_plot(meteo_values)
    _create_precipitation_60_hours_plot(precipitation_3_hours_values)
    _create_precipitation_9_days_plot(precipitation_6_hours_values)
    fig.tight_layout(h_pad=3.5)
    return fig.savefig(os.path.join(PLOT_PATH, 'plot.png'))


def _create_temperature_plot(values):
    times = [time[0] for time in values]
    values = [value[2] for value in values]
    plt.subplot(511)
    plt.plot(times, values, 'r-')
    plt.title("Temperatura", fontsize=11)
    plt.ylabel("[C]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()
    return plt

def _create_pressure_plot(values):
    times = [time[0] for time in values]
    values = [value[3] for value in values]
    plt.subplot(512)
    plt.plot(times, values, 'g-')
    plt.title("Ciśnienie", fontsize=11)
    plt.ylabel("[hPa]")
    plt.xlabel('')
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    return plt

def _create_humidity_plot(values):
    times = [time[0] for time in values]
    values = [value[4] for value in values]
    plt.subplot(513)
    plt.xticks()
    plt.plot(times, values, 'b-')
    plt.title("Wilgotność", fontsize=11)
    plt.ylabel("[%]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    return plt

def _create_precipitation_60_hours_plot(values):
    times = [time[0] for time in values]
    values = [value[1] for value in values]
    plt.subplot(514)
    plt.bar(times, values, width=0.1, alpha=1.0, color=['grey'])
    plt.title("Wysokość opadu (prognoza na 60 godzin)", fontsize=11)
    plt.ylabel("[mm]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()
    return plt

def _create_precipitation_9_days_plot(values):
    times = [time[0] for time in values]
    values = [value[1] for value in values]
    plt.subplot(515)
    plt.bar(times, values, width=0.150, alpha=1.0, color=['grey'])
    plt.title("Wysokość opadu (prognoza na 9 dni)", fontsize=11)
    plt.ylabel("[mm]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()
    return plt

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

    lat = location[0]
    lng = location[1]
    country = location[2]

    url = _get_url(FORECAST_URL, lat, lng)
    meteo_parameters = _get_data(url)[0]
    precipitation_parameters = _get_data(url)[1]

    current_time = datetime.now()
    current_location_time = get_current_location_time(lat, lng)[1]
    current_temperature = meteo_parameters[0][2]
    current_pressure = meteo_parameters[0][3]
    current_humidity = meteo_parameters[0][4]
    current_precipitation = float(precipitation_6_hours_values[0][1])
    current_cloudiness = float(meteo_parameters[0][5])

    time_of_day = get_time_of_day(lat, lng)
    _create_plots(meteo_parameters, precipitation_3_hours_values,precipitation_6_hours_values,)

    Lat = str(lat).replace(',', '.')
    Lng = str(lng).replace(',', '.')
    pora = 'noc'

    current_location_time_display_value = current_location_time_display(current_location_time)




    times = [time[0] for time in meteo_parameters]
    len_times = len(times)
    times_tuples = []
    for i in range(len_times):
        time = times[i]
        time_tuple = ([time.month, time.day, time.year, time.hour, time.minute])
        times_tuples.append(time_tuple)
    temp_values_str = [value[2] for value in meteo_parameters]
    temp_values = [float(value) for value in temp_values_str]
    press_values = [float(value[3]) for value in meteo_parameters]
    hum_values = [float(value[4]) for value in meteo_parameters]


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
        'current_precipitation': current_precipitation,
        'current_cloudiness': current_cloudiness,
        'url': url,
        'data': meteo_parameters,
        'data1': precipitation_6_hours_values,
        'data2': precipitation_3_hours_values,
        'len_times': len_times,
        'temperature_values': temp_values,
        'times_tuples': times_tuples,
        'pressure_values': press_values,
        'humidity_values': hum_values,
        'precipitation_6_hours_values': precip_6_values,
        'precipitation_3_hours_values': precip_3_values,
    }
    return render(request, "forecast/details.html", context)

def plots(request):
    plot_times = []
    for i in range(10):
        time = datetime.now() + timedelta(hours=i) + timedelta(hours=2)
        time_tuples = ([time.month, time.day, time.year, time.hour, time.minute])
        plot_times.append(time_tuples)
    plot_values = [1, 4, 1, 4, 7, 9, 7, 3, 4]

    context = {
        'times': plot_times,
        'values': plot_values,
    }
    return render(request, "forecast/plot.html", context)
