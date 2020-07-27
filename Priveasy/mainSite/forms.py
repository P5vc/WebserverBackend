from django import forms
from django.contrib.auth.models import User


class UserRegistrationForm(forms.ModelForm):
	password = forms.CharField(label = 'Password' , widget = forms.PasswordInput)
	passwordAgain = forms.CharField(label = 'Repeat Password' , widget = forms.PasswordInput)

	class Meta:
		model = User
		fields = ('username' , 'first_name' , 'email')

	def cleanPasswordAgain(self):
		cd = self.cleaned_data
		if (cd['password'] != cd['passwordAgain']):
			raise forms.ValidationError('Passwords do not match.')
		return cd['passwordAgain']


class LoginForm(forms.Form):
	username = forms.CharField()
	password = forms.CharField(widget = forms.PasswordInput)


class TextSendForm(forms.Form):
	recipientNumber = forms.CharField(label = 'recipientNumber' , max_length = 11)
	message = forms.CharField(widget = forms.Textarea , max_length = 140)
