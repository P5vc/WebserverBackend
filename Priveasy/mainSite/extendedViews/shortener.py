from django.http import HttpResponse , Http404
from django.shortcuts import redirect
from ..models import Stats , ShortenedURL
from .generic404 import p5vcNotFound


def short(request , slug = ''):
	'''
	Returns a redirect to the proper, destination URL.

	This function accepts HTTP requests for a shortened URL, then returns the
	appropriate HTTP 301 redirect response, redirecting to the proper,
	full-length URL.

	Accepts:
		request (django.http.HttpRequest): HttpRequest object to be processed
		slug (str): A string containing the shortened URL ID

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	if (request.META['HTTP_HOST'] == 'p5.vc'):
		try:
			# Update click statistics:
			urlObj = ShortenedURL.objects.get(slug = slug)
			urlObj.clicks += 1
			urlObj.save()

			# Update page statistics:
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.shortenedURLClicks += 1
			pageStatsObj.save()

			return redirect(urlObj.destinationURL , permanent = True)
		except:
			if (len(slug) == 6):
				return HttpResponse('This URL does not exist or has been removed.')
			else:
				return p5vcNotFound()
	else:
		# Update page statistics:
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.priveasy404Views += 1
		pageStatsObj.save()

		raise Http404('The requested page does not exist.')
