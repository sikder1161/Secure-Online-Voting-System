from django import forms
from .models import Election, Candidate

class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ('title', 'description', 'starts_at', 'ends_at', 'status')
        widgets = {
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ('starts_at', 'ends_at'):
            self.fields[key].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
        self.fields['status'].choices = [
            ('DRAFT', 'Draft'), ('SCHEDULED', 'Scheduled')
        ]

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ('name', 'information')
