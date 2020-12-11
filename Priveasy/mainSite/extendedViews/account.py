from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator , EmailValidator
from django.shortcuts import render , redirect
from ..models import Stats , Paste , ShortenedURL , EmailForwarder
from ..forms import TextSendForm
from ..tasks import sendText , sendEmail
from .generic404 import p5vcNotFound
from .permissions import checkPermission
import time


@login_required
def account(request):
	'''
	Returns an HTTP response to requests sent to the account page.

	This function accepts GET and POST requests sent to the account page,
	processes them, completes any necessary actions, then renders and returns
	an appropriate HTTP response.

	Accepts:
		request (django.http.HttpRequest): HttpRequest object to be processed

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# If host is p5.vc, return the appropriate response:
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()


	# Process GET requests:
	if (request.method == 'GET'):
		# Update page statistics:
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.accountViews += 1
		pageStatsObj.save()

		# Collect template data:
		hasPlan = False
		if (request.user.accountcontents.planType > 0):
			hasPlan = True

		planExpiration = (request.user.accountcontents.planExpiration - int(time.time()))
		daysLeft = int(((planExpiration / 60) / 60) / 24)
		hoursLeft = (int((planExpiration / 60) / 60) - (daysLeft * 24))

		pasteSlideList = [0]
		pasteList = []
		counter = 0
		for paste in (Paste.objects.filter(account = request.user.accountcontents)):
			if (counter != 0):
				pasteSlideList.append(counter)
			pasteList.append(paste)
			counter += 1

		hasURLs = False
		urlList = []
		for url in (ShortenedURL.objects.filter(account = request.user.accountcontents)):
			urlList.append(url)
		if (len(urlList) > 0):
			hasURLs = True

		hasForwarders = False
		forwarderList = []
		for forwarder in (EmailForwarder.objects.filter(account = request.user.accountcontents)):
			forwarderList.append(forwarder)
		if (len(forwarderList) > 0):
			hasForwarders = True

		return render(request , 'account.html' , {'hasPlan' : hasPlan , 'daysLeft' : daysLeft , 'hoursLeft' : hoursLeft , 'pasteSlideList' : pasteSlideList , 'pasteList' : pasteList , 'hasURLs' : hasURLs , 'urlList' : urlList , 'hasForwarders' : hasForwarders , 'forwarderList' : forwarderList})


	# Process POST requests:
	if (request.method == 'POST'):
		# Detect which service/element the post request applies to:
		if ('paste' in request.POST):
			return handlePastes(request)
		elif ('url' in request.POST):
			return handleShortenedURLs(request)
		elif ('deleteURL' in request.POST):
			return deleteShortenedURL(request)
		elif ('recipientNumber' in request.POST):
			return handleTexts(request)
		elif ('recipient' in request.POST):
			return handleBurnerEmails(request)
		elif ('forwarder' in request.POST):
			return handleEmailForwarders(request)
		elif ('deleteForwarder' in request.POST):
			return deleteEmailForwarder(request)
		elif ('token' in request.POST):
			return forwarderVerification(request)
		else:
			return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. An invalid POST request was received. If this error continues, please contact Support'})


	# Provide a generic, default response:
	return redirect('account')


def handlePastes(request):
	'''
	Saves paste data then returns an HTTP response.

	This function accepts a POST, HTTP request object containing paste data
	from the account function, then processes the data and saves it. Once the
	data has been saved (or an error occurs), the appropriate HTTP response is
	returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		paste data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	try:
		# Make sure the user has proper permissions to use the pastebin service:
		if (not(checkPermission('pastebin' , request.user))):
			return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You must have a plan to use this feature.'})

		pasteObj = Paste.objects.filter(account = request.user.accountcontents).get(pasteID = str(request.POST['pasteID']))
		# Automatically remove any extra, empty pastes (leaving just one per account):
		if (len(request.POST['paste']) == 0):
			if (len(Paste.objects.filter(account = request.user.accountcontents , contents = '')) > 0):
				pasteObj.delete()
				return redirect('account')

		if (int(request.POST['public']) == 1):
			# Make sure the user has the appropriate permissions to make the paste public:
			if (checkPermission('publicPaste' , request.user)):
				pasteObj.public = True
			else:
				pasteObj.public = False
		else:
			pasteObj.public = False

		pasteObj.contents = str(request.POST['paste'])
		pasteObj.save()

		# If the user hasn't exceeded the maximum number of pastes, create a new, blank one for them to use next time:
		if ((Paste.objects.filter(account = request.user.accountcontents).count() < 100) and (len(Paste.objects.filter(account = request.user.accountcontents , contents = '')) == 0)):
			Paste.objects.create(account = request.user.accountcontents)
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Paste Not Saved.'})

	return redirect('account')


def handleShortenedURLs(request):
	'''
	Creates shortened URLs, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing a URL a shorten, then assigns the URL to a new
	ShortenedURL object and saves it. Once the data has been saved (or an
	error occurs), the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		URL data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has proper permissions to use the URL shortening service:
	if (not(checkPermission('urlShortener' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You must have a plan to use this feature.'})

	# Limit the number of URLs that may be shortened per plan:
	if (checkPermission('canHave5URLs' , request.user)):
		if (checkPermission('canHave15URLs' , request.user)):
			if (checkPermission('canHave100URLs' , request.user)):
				if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 100):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
			else:
				if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 15):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
		else:
			if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 5):
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
	else:
		return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. URL Not Saved.'})

	# Save the shortened URL:
	try:
		validate = URLValidator()
		validate(str(request.POST['url']))
		ShortenedURL.objects.create(account = request.user.accountcontents , destinationURL = str(request.POST['url']))
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 8 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Invalid URL entered. You may have forgotten the "https://" at the beginning.'})

	return redirect('account')


def deleteShortenedURL(request):
	'''
	Deletes shortened URLs, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing a shortened URL to delete, then deletes it. Then, the
	appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		URL data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has proper permissions to use the URL shortening service:
	if (not(checkPermission('urlShortener' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You must have a plan to use this feature.'})

	# Delete the corresponding ShortenedURL object:
	try:
		urlObj = ShortenedURL.objects.get(account = request.user.accountcontents , slug = str(request.POST['deleteURL']))
		urlObj.delete()
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})

	return redirect('account')


def handleTexts(request):
	'''
	Sends burner text messages, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing burner text data. That data is then evaluated for
	validity and sent. Afterwards, the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		text message data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has proper permissions to use the burner text messaging service:
	if (not(checkPermission('textMessaging' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Your plan does not include this service.'})

	if (checkPermission('textsRemaining' , request.user)):
		textForm = TextSendForm(request.POST)
		if (textForm.is_valid()):
			cd = textForm.cleaned_data
			toNumber = cd['recipientNumber']
			message = cd['message']


			# Validate the text message body (length is less than 140 characters, and only valid characters are used):
			messageLength = len(message)
			# Some characters add two to the message length:
			for char in message:
				if ((char == '\n') or (char == '\r')):
					messageLength += 1

			if (messageLength <= 140):
				validChars = '@ 0¡P¿p£_!1AQaq$Φ"2BRbr¥Γ\\#3CScsèΛ¤4DTdtéΩ%5EUeuùΠ&6FVfvìΨ\'7GWgwòΣ(8HXhxÇΘ)9IYiy\n\rΞ*:JZjzØ+;KÄkäøÆ,<LÖlöæ-=MÑmñÅß.>NÜnüåÉ/?O§oà'
				validMessage = True
				for char in message:
					if (not(char in validChars)):
						validMessage = False
						break
				if (validMessage):
					message += '\n\n- Priveasy User'
					request.user.accountcontents.textsRemaining -= 1
					request.user.accountcontents.save()
					sendText.delay(cd['recipientNumber'] , message)
					return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Text Sent' , 'message' : 'Text Successfully Sent'})
				else:
					return render(request , 'fullscreenMessage.html' , {'delay' : 6 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. Invalid characters used. Note: emojis are not supported.'})
			else:
				return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. Message body exceeds 140 characters.'})
		else:
			return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. Invalid submission. Please try again.'})
	else:
		return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. You do not have any sends left.'})


def handleBurnerEmails(request):
	'''
	Sends burner emails, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing burner email data. That data is then evaluated for
	validity and sent. Afterwards, the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		burner email data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has proper permissions to send burner emails:
	if (not(checkPermission('burnerEmail' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Your plan does not include this service.'})

	# Make sure the user has enough burner email sends remaining:
	if (not(checkPermission('emailsRemaining' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Unable to send message. You have no burner email sends remaining.'})

	# Determine if the "from" address should be randomized or a valid forwarder:
	fromAddress = ''
	if (checkPermission('sendFromForwarder' , request.user)):
		if (str(request.POST['sender']) != 'Burner'):
			try:
				fwdObj = EmailForwarder.objects.get(account = request.user.accountcontents , forwarder = str(request.POST['sender']))
				fromAddress = fwdObj.forwarder
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Unable to send from that address.'})

	if (not(fromAddress)):
		fromAddress = ((str(uuid.uuid4()).replace('-' , ''))[0:10] + '@Burn.Priveasy.org')

	sendEmail.delay(request.POST['subject'] , request.POST['message'] , fromAddress , [request.POST['recipient']])
	request.user.accountcontents.emailsRemaining -= 1
	request.user.accountcontents.save()

	return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! Your email has been sent!'})


def handleEmailForwarders(request):
	'''
	Saves email forwarders, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing email forwarder data. That data is then evaluated for
	validity and saved. Afterwards, the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		email forwarder data

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has the proper permissions to create email forwarders:
	if (not(checkPermission('emailForwarder' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Your plan does not include this service.'})

	# Limit the number of email forwarders per plan:
	if (checkPermission('canHave3Forwarders' , request.user)):
		if (checkPermission('canHave5Forwarders' , request.user)):
			if (checkPermission('canHave25Forwarders' , request.user)):
				if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 25):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
			else:
				if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 5):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
		else:
			if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 3):
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
	else:
		return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Forwarder Not Saved.'})

	# Create and save the forwarder:
	try:
		validate = EmailValidator()
		validate(str(request.POST['forwarder']))
		fwdObj = EmailForwarder.objects.create(account = request.user.accountcontents , forwardTo = str(request.POST['forwarder']))
		with open('/home/ubuntu/Priveasy/mainSite/templates/email/fwdEmailConfirm.html' , 'r') as fwdEmailConfirmText:
			emailText = ((fwdEmailConfirmText.read()).replace('~' , fwdObj.verifID)).replace('`' , request.user.first_name)
			sendEmail.delay('Email Forwarding Verification' , emailText , 'EmailVerification@NoReply.Priveasy.org' , [fwdObj.forwardTo] , subType = 'html')
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Invalid Email Address Entered'})

	return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! Check your inbox (or spam folder) for the verification email.'})


def deleteEmailForwarder(request):
	'''
	Deletes an email forwarder, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, specifying an email forwarder to delete. The corresponding
	forwarder is then deleted, and the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object specifying
		email forwarder to delete

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has the proper permissions to delete email forwarders:
	if (not(checkPermission('emailForwarder' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Your plan does not include this service.'})

	# Delete the specified forwarder:
	try:
		forwarderObj = EmailForwarder.objects.get(account = request.user.accountcontents , forwarder = str(request.POST['deleteForwarder']))
		forwarderObj.delete()
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Unable to delete the specified forwarder.'})

	return redirect('account')


def forwarderVerification(request):
	'''
	Verifies an email forwarder, then returns an HTTP response.

	This function accepts a POST, HTTP request object from the account
	function, containing a unique verification code used to verify ownership of
	the destination email address of an email forwarder. The verified state is
	then saved, and the appropriate HTTP response is returned.

	Accepts:
		request (django.http.HttpRequest): POST HttpRequest object containing
		an email forwarder verification token

	Returns:
		(django.http.HttpResponse): Appropriate HttpResponse object
	'''

	# Make sure the user has the proper permissions to use email forwarders:
	if (not(checkPermission('emailForwarder' , request.user))):
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Your plan does not include this service.'})

	try:
		forwarderObj = EmailForwarder.objects.get(account = request.user.accountcontents , verifID = str(request.POST['token']))
		forwarderObj.verified = True
		forwarderObj.save()
		return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! This forwarder will be activated within 15 minutes!'})
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Failed' , 'message' : 'Error. This token is invalid. Please try again.'})
