#PrognozaPogody

PrognozaPogody is a simple application to check weather forecast in a specific place. PrognozaPogody provides information about actual weather parameter, localization of your place and predicted temperature, atmospheric pressure, humidity and height of precipitation.

##Installation in local virtual environment
Install python 3, virtualenv and git 
```
$ sudo apt-get install python3 virtualenv git
```
Setup a new virtualenv with python3
```
$ virtualenv -p /usr/bin/python3 <virtualenv_name>
$ cd <virtualenv_name>
```
Check virtualenv python version
```
$ python -V
```
You should have 3.x.x version.
Clone the repository from github
```
$ git clone https://github.com/elangaar/django-weather-forecast.git
```
Activate your virtual environment, go to the project directory and install requirements using pip:
```
$ source bin/activate
$ cd django-weather-forecast
$ pip install -r Requirements.txt
```
Collect the static files into STATIC_ROOT
```
$ python manage.py collectstatic
```
Run the project starting development server (default on port 8000):
```
$ python manage.py runserver
``` 

##License

WeatherForecast is licensed under the terms of the MIT License (see the file LICENSE).
