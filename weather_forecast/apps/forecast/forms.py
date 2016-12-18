from django import forms

class SelectForm(forms.Form):
    name = forms.CharField(label="Nazwa miejsca", max_length=30)
