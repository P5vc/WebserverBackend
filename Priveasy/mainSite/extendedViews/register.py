from django.forms import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import render , redirect
from ..models import Stats , AccountContents , ReferralCode , Paste , ZcashPaymentAddresses
from ..forms import UserRegistrationForm
from .generic404 import p5vcNotFound

def register(request):
	'''
	Returns an HTTP response to requests sent to the register page.

	This function accepts GET and POST requests sent to the register page,
	processes them, completes any necessary actions, then renders and returns
	an appropriate HTTP response.

	Accepts:
		(django.http.HttpResponse): HttpRequest object to be processed

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# If host is p5.vc, return the appropriate response:
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()


	# Process GET requests:
	if (request.method == 'GET'):
		# Update page statistics
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.registerViews += 1
		pageStatsObj.save()

		return render(request , 'register.html' , {'errors' : []})


	# Process POST requests:
	if (request.method == 'POST'):
		# Force case-insensitive usernames:
		requestData = {}
		for field in request.POST:
			requestData[field] = request.POST[field]
		requestData['username'] = requestData['username'].lower()

		userForm = UserRegistrationForm(requestData)

		if (userForm.is_valid()):
			if (len(userForm.cleaned_data['username']) < 4):
				userForm.add_error('username' , ValidationError('Usernames must be at least four characters in length'))
				return render(request , 'register.html' , {'errors' : list(userForm.errors.values())})
			if (not(userForm.cleaned_data['password'] == userForm.cleaned_data['passwordAgain'])):
				userForm.add_error('passwordAgain' , ValidationError('Passwords do not match'))
				return render(request , 'register.html' , {'errors' : list(userForm.errors.values())})

			try:
				validate_password(userForm.cleaned_data['password'])
			except Exception as error:
				userForm.add_error('password' , error)
				return render(request , 'register.html' , {'errors' : list(userForm.errors.values())})

			newUser = userForm.save(commit = False)
			newUser.set_password(userForm.cleaned_data['password'])
			newUser.save()
			newUserAccount = AccountContents.objects.create(user = newUser)
			newUserReferralCode = ReferralCode.objects.create(account = newUserAccount)
			newEmptyPaste = Paste.objects.create(account = newUserAccount)
			newZcashAddresses = ZcashPaymentAddresses.objects.create(account = newUserAccount)

			return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('home') , 'title' : 'Welcome!' , 'message' : ('Welcome, ' + newUser.username)})
		else:
			return render(request , 'register.html' , {'errors' : list(userForm.errors.values())})


	# Provide a generic response:
	return redirect('register')
