from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from ..models import Stats , VPNProfile
from ..tasks import sendEmail
from .generic404 import p5vcNotFound
from .permissions import checkPermission
from io import BytesIO


@login_required
def vpnDownload(request , slug = ''):
	'''
	Returns an HTTP response with a VPN configuration file or data.

	This function accepts HTTP requests for specific, VPN configuration
	information, then returns the appropriate HTTP response, allowing the user
	to view or download the appropriate information.

	Accepts:
		request (django.http.HttpRequest): HttpRequest object to be processed
		slug (str): A string containing the VPN profile ID

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# If host is p5.vc, return the appropriate response:
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()


	# Check if the user has the proper permissions to use this service:
	if (not(checkPermission('VPN' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error: Your plan does not include VPN access.'})


	slugToVPNprofile = {'1' : '.conf' , '2' : '.mobileconfig' , 'a' : [1 , '-1' , 'dom1'] , 'b' : [1 , '-2' , 'dom2'] , 'c' : [1 , '-3' , 'dom3'] , 'd' : [1 , '-4' , 'dom4'] , 'e' : [1 , '-5' , 'dom5'] , 'f' : [2 , '-1' , 'off1'] , 'g' : [2 , '-2' , 'off2'] , 'h' : [2 , '-3' , 'off3'] , 'i' : [2 , '-4' , 'off4'] , 'j' : [2 , '-5' , 'off5']}

	try:
		# Send an email with installation instructions:
		if (slug == '0'):
			emailContents = ''
			with open('/home/ubuntu/Priveasy/mainSite/templates/email/vpnEmail.html' , 'r') as emailFile:
				emailContents = emailFile.read()
			sendEmail.delay('VPN Installation Instructions' , emailContents , 'VPN@NoReply.Priveasy.org' , [request.user.email] , subType = 'html')
			return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! The email has been sent!'})
		# Supply appropriate, VPN profile download URLs:
		elif ((slug == '1') or (slug == '2')):
			return render(request , 'vpnSelection.html' , {'slug1' : (slug + 'a') , 'slug2' : (slug + 'b') , 'slug3' : (slug + 'c') , 'slug4' : (slug + 'd') , 'slug5' : (slug + 'e') , 'slug6' : (slug + 'f') , 'slug7' : (slug + 'g') , 'slug8' : (slug + 'h') , 'slug9' : (slug + 'i') , 'slug10' : (slug + 'j')})
		# Show Shadowsocks connection information:
		elif (slug == '3'):
			if (checkPermission('Shadowsocks' , request.user)):
				returnContents = '<!DOCTYPE html>\n<html lang="en">\n<body>\n<pre>'
				profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
				profileObj = profileObj[0]
				try:
					with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/Shadowsocks/' + profileObj.vpnUsername + '.conf') , 'r') as file:
						returnContents += ('########## DOMESTIC SERVER ##########\n\n' + file.read() + '\n#####################################\n\n')
				except:
					returnContents += 'AN ERROR OCCURRED WHILE FETCHING THE DOMESTIC SERVER CONNECTION DETAILS\n\n'

				profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
				profileObj = profileObj[0]
				try:
					with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/Shadowsocks/' + profileObj.vpnUsername + '.conf') , 'r') as file:
						returnContents += ('\n########## OFFSHORE SERVER ##########\n\n' + file.read() + '\n#####################################')
				except:
					returnContents += 'AN ERROR OCCURRED WHILE FETCHING THE OFFSHORE SERVER CONNECTION DETAILS'

				returnContents += '\n</pre>\n</body>\n</html>'

				pageStatsObj = Stats.objects.get(id = 1)
				pageStatsObj.shadowsocksViews += 1
				pageStatsObj.save()

				return HttpResponse(returnContents)
			else:
				return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error: Your plan does not include Shadowsocks access.'})
		# Allow the requested VPN profile to be downloaded:
		elif (((len(slug == 2)) and (slug[0] in '12')) and (slug[1] in 'abcdefghij')):
			if (not(checkPermission(('VPN-' + slug[1]) , request.user))):
				return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error: Your plan does not include these VPN profiles.'})

			ioObj = BytesIO()
			profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = slugToVPNprofile[slug[1]][0])
			profileObj = profileObj[0]
			with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + slugToVPNprofile[slug[1]][1] + slugToVPNprofile[slug[0]]) , 'rb') as file:
				ioObj.write(file.read())
			response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
			response['Content-Disposition'] = ('attachment; filename=PriveasyVPN' + slugToVPNprofile[slug[1]][2] + slugToVPNprofile[slug[0]])
			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.vpnDownloads += 1
			pageStatsObj.save()
			return response
		else:
			return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error! The URL you entered was invalid.'})
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 15 , 'redirectURL' : reverse('account') , 'title' : 'Maintenance' , 'message' : 'The requested VPN profile may not have been sent from the VPN server to this webserver yet. Please try again in a few hours. If this message persists for more than 24 hours, please contact support.'})
