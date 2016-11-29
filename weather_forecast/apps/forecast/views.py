from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.text import slugify

from .forms import SelectForm


def select(request):
    if request.method == "POST":
        form = SelectForm(request.POST)
        if form.is_valid():
            name = request.POST['name']
            if name == '':
                messages.error(request, 'Wprowadź nazwę miejscowości!')
                return redirect(reverse('select'))
            slug = slugify(name)
            request.session['name'] = name
            return HttpResponseRedirect(
                reverse('forecast-details', args=(slug, ))
            )
    else:
        form = SelectForm()
    return render(request, "forecast/index.html", {'form':form})


def forecast_details(request, slug):

    request.session.modified = True
    name = request.session.pop('name')
    return HttpResponse('<p> Jest dobrze! </p>')
