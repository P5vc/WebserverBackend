from django.http import HttpResponse
from ..models import Stats


def p5vcNotFound():
	'''
	Returns a generic, Error 404 HTTP response.

	This function is meant to return a generic, Error 404 message whenever a
	request is made for an invalid, "p5.vc" URL. Before returning the
	HttpResponse, the appropriate page statistics counter will be incremented
	by one and saved.

	Accepts:
		This function does not accept any arguments.

	Returns:
		(django.http.HttpResponse): HttpResponse object with 404 status code
		and generic, "Not Found" HTML
	'''

	pageStatsObj = Stats.objects.get(id = 1)
	pageStatsObj.p5vc404Views += 1
	pageStatsObj.save()
	return HttpResponse('\n<!doctype html>\n<html lang="en">\n<head>\n  <title>Not Found</title>\n</head>\n<body>\n  <h1>Not Found</h1><p>The requested resource was not found on this server.</p>\n</body>\n</html>\n' , status = 404)
