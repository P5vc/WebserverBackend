from django.http import HttpResponse
from ..models import Paste , Stats
from .generic404 import p5vcNotFound


def pastes(request , slug = ''):
	'''
	Returns the raw contents of the requested, public paste.

	This function accepts GET requests for public pastes, and then returns an
	HTTP response with the raw contents of the desired paste.

	Accepts:
		request (django.http.HttpRequest): HttpRequest object to be processed
		slug (str): A string containing the ID of the paste being requested

	Returns:
		(django.http.HttpResponse): HttpResponse object with raw, paste
		contents
	'''

	# If host is p5.vc, return the appropriate response:
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()

	# Process GET requests:
	if (request.method == 'GET'):
		try:
			paste = Paste.objects.get(pasteID = slug , public = True)

			# Update paste statistics:
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.publicPasteViews += 1
			pageStatsObj.save()

			return HttpResponse(str(paste.contents))
		except:
			return HttpResponse('No paste found at this URL.')
	else:
		return HttpResponse('Error: Not a GET request.')
