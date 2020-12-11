from django.http import Http404
from django.shortcuts import render , redirect
from ..models import Stats
from .generic404 import p5vcNotFound


def policies(request , slug = ''):
	'''
	Returns an HTTP response containing the requested policy.

	This function accepts GET requests for policy documentation, then returns
	the appropriate, HTTP response containing the requested policy.

	Accepts:
		request (django.http.HttpRequest): HttpRequest object to be processed
		slug (str): A string containing the ID of the requested policy

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# If host is p5.vc, return the appropriate response:
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()


	# Process GET requests:
	if (request.method == 'GET'):
		if (slug == '1'):
			# Update page statistics:
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.privacyPolicyViews += 1
			pageStatsObj.save()

			return render(request , 'policies/PrivacyPolicy.html' , {})
		elif (slug == '2'):
			# Update page statistics:
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.termsViews += 1
			pageStatsObj.save()

			return render(request , 'policies/TermsOfService.html' , {})
		else:
			# Update page statistics:
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.priveasy404Views += 1
			pageStatsObj.save()

			raise Http404('The requested page does not exist.')


	# Provide a generic, default response:
	return redirect('home')
