from django.contrib.auth import authenticate , login
from django.shortcuts import render , redirect
from ..models import Stats , VPNServer
from ..forms import LoginForm
from .generic404 import p5vcNotFound

def home(request):
	'''
	Returns an HTTP response to requests sent to the home page.

	This function accepts GET and POST requests sent to the home page,
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
		pageStatsObj.homeViews += 1
		pageStatsObj.save()

		# Collect template data:
		ipAddr = request.META['REMOTE_ADDR']
		host = request.META['HTTP_HOST']

		if (len(VPNServer.objects.filter(serverIP = ipAddr)) == 1):
			isUsingVPN = True
		else:
			isUsingVPN = False

		return render(request , 'home.html' , {'isUsingVPN' : isUsingVPN})

	# Process POST requests:
	if (request.method == 'POST'):
		form = LoginForm(request.POST)

		if (form.is_valid()):
			cd = form.cleaned_data
			user = authenticate(request , username = cd['username'].lower() , password = cd['password'])
			if (user == None):
				return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('home') , 'title' : 'Invalid Login' , 'message' : 'Invalid Login'})
			else:
				if (user.is_active):
					login(request , user)
					return redirect('account')
				else:
					return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('home') , 'title' : 'Account Disabled' , 'message' : 'Disabled Account'})


	# Provide a generic response:
	return redirect('home')
