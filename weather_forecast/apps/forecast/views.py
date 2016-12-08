from urllib.request import urlopen
import re
from datetime import datetime, timedelta
import os


from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.text import slugify
from django.contrib import messages
from django.template.loader import render_to_string


from geopy.geocoders import Nominatim
import xmltodict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from PIL import Image

from .forms import SelectForm
from weather_forecast.settings import BASE_DIR
from weather_forecast.apps.forecast.models import Waypoint



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

def _create_temperature_plot(values):
    times = [time[0] for time in values]
    values = [value[2] for value in values]
    plt.plot(times, values, 'r-')
    plt.title("Temperatura", fontsize=11)
    plt.ylabel("[C]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    plt.savefig(os.path.join(PLOT_PATH, 'temperature_plot.png'))

def _create_pressure_plot(values):
    times = [time[0] for time in values]
    values = [value[3] for value in values]
    plt.plot(times, values, 'g-')
    plt.title("Ciśnienie", fontsize=11)
    plt.ylabel("[hPa]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    plt.savefig(os.path.join(PLOT_PATH, 'pressure_plot.png'))

def _create_humidity_plot(values):
    times = [time[0] for time in values]
    values = [value[4] for value in values]
    plt.plot(times, values, 'b-')
    plt.title("Wilgotność", fontsize=11)
    plt.ylabel("[%]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    plt.savefig(os.path.join(PLOT_PATH, 'humidity_plot.png'))

def _create_precipitation_60_hours_plot(values):
    times = [time[0] for time in values]
    values = [value[1] for value in values]
    plt.bar(times, values, width=0.125, alpha=1.0, color=['grey'])
    plt.title("Wysokość opadu (prognoza na 60 godzin)", fontsize=11)
    plt.ylabel("[mm]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(interval=6))
    plt.gcf().autofmt_xdate()
    plt.savefig(os.path.join(PLOT_PATH, 'precipitation_60_hours_plot.png'))

def _create_precipitation_9_days_plot(values):
    times = [time[0] for time in values]
    values = [value[1] for value in values]
    plt.bar(times, values, width=0.125, alpha=1.0, color=['grey'])
    plt.title("Wysokość opadu (prognoza na 9 dni)", fontsize=11)
    plt.ylabel("[mm]")
    plt.grid(True, linestyle="-", linewidth="0.2")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()
    plt.savefig(os.path.join(PLOT_PATH, 'precipitation_9_days_plot.png'))

def forecast_details(request, slug):
    request.session.modified = True
    name = request.session.pop('name').capitalize()
    try:
        location = _coordinates(name)
    except AttributeError:
        messages.error(request, "Wprowadź poprawną nazwę miasta/miejscowości!")
        return redirect(reverse('select'))

    lat = location[0]
    lng = location[1]

    url = _get_url(FORECAST_URL, lat, lng)
    meteo_parameters = _get_data(url)[0]
    precipitation_parameters = _get_data(url)[1]

    current_time = meteo_parameters[0][0]
    current_temperature = meteo_parameters[0][2]
    current_pressure = meteo_parameters[0][3]
    current_humidity = meteo_parameters[0][4]
    current_precipitation = precipitation_6_hours_values[1]
    current_cloudiness = meteo_parameters[0][5]

    _create_temperature_plot(meteo_parameters)
    _create_pressure_plot(meteo_parameters)
    _create_humidity_plot(meteo_parameters)
    _create_precipitation_60_hours_plot(precipitation_3_hours_values)
    _create_precipitation_9_days_plot(precipitation_6_hours_values)

    Lat = str(lat).replace(',', '.')
    Lng = str(lng).replace(',', '.')
    waypoints = Waypoint.objects.create(name=name, geometry='POINT({}\
                                       {})'.format(Lat, Lng)).save()
    context = {
        'name': name,
        'lat': lat,
        'lng': lng,
        'Lat': Lat,
        'Lng': Lng,
        'current_time': current_time,
        'current_temperature': current_temperature,
        'current_pressure': current_pressure,
        'current_humidity': current_humidity,
        'current_precipitation': current_precipitation,
        'current_cloudiness': current_cloudiness,
        'url': url,
        'data': meteo_parameters,
        'data1': precipitation_6_hours_values,
        'data2': precipitation_3_hours_values,
        'content': render_to_string("forecast/waypoints.html", {'waypoints':
                                                                waypoints})

    }
    return render(request, "forecast/details.html", context)
