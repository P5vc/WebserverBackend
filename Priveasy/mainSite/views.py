from django.shortcuts import render , redirect
from django.http import HttpResponse , Http404
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate , login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator , EmailValidator
from django.conf import settings
from .models import *
from .forms import *
from .tasks import sendText , sendEmail
import stripe
from io import BytesIO
import time , uuid , requests

def p5vcNotFound():
	pageStatsObj = Stats.objects.get(id = 1)
	pageStatsObj.p5vc404Views += 1
	pageStatsObj.save()
	return HttpResponse('\n<!doctype html>\n<html lang="en">\n<head>\n  <title>Not Found</title>\n</head>\n<body>\n  <h1>Not Found</h1><p>The requested resource was not found on this server.</p>\n</body>\n</html>\n' , status = 404)


def home(request):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()

	if (request.method == 'GET'):
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.homeViews += 1
		pageStatsObj.save()

		ipAddr = request.META['REMOTE_ADDR']
		host = request.META['HTTP_HOST']
		knownTor = False
		if (host == 'priveasy6qxoehbhq5nxcxv35y6el73hpzpda7wgtnfe5qaspemtl6qd.onion'):
			knownTor = True
		if (len(VPNServer.objects.filter(serverIP = ipAddr)) == 1):
			isUsingVPN = True
		else:
			isUsingVPN = False

		return render(request , 'home.html' , {'isUsingVPN' : isUsingVPN , 'knownTor' : knownTor})

	elif (request.method == 'POST'):
		form = LoginForm(request.POST)
		if (form.is_valid()):
			cd = form.cleaned_data
			user = authenticate(request , username = cd['username'].lower() , password = cd['password'])
			if (user == None):
				return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('home') , 'title' : 'Invalid Login' , 'message' : 'Invalid Login'})
			else:
				if (user.is_active):
					login(request , user)
					return render(request , 'fullscreenMessage.html' , {'delay' : 1 , 'redirectURL' : reverse('account') , 'title' : 'Logged In' , 'message' : 'Authenticated Successfully'})
				else:
					return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('home') , 'title' : 'Account Disabled' , 'message' : 'Disabled Account'})

		return redirect('home')

	else:
		return redirect('home')


def register(request):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		return p5vcNotFound()

	if (request.method == 'GET'):
		return render(request , 'register.html' , {'errors' : []})

	elif (request.method == 'POST'):
		# Force case-insensitive usernames:
		requestData = {}
		for field in request.POST:
			requestData[field] = request.POST[field]
		requestData['username'] = requestData['username'].lower()

		userForm = UserRegistrationForm(requestData)

		if (userForm.is_valid()):
			if (len(userForm.cleaned_data['username']) < 4):
				userForm.add_error('username' , forms.ValidationError('Usernames must be at least four characters in length'))
				return render(request , 'register.html' , {'errors' : list(userForm.errors.values())})
			if (not(userForm.cleaned_data['password'] == userForm.cleaned_data['passwordAgain'])):
				userForm.add_error('passwordAgain' , forms.ValidationError('Passwords do not match'))
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

	else:
		return redirect('register')


@login_required
def account(request):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	if (request.method == 'GET'):
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.accountViews += 1
		pageStatsObj.save()

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

	elif (request.method == 'POST'):
		if ('paste' in request.POST):
			try:
				pasteObj = Paste.objects.filter(account = request.user.accountcontents).get(pasteID = str(request.POST['pasteID']))
				if (len(request.POST['paste']) == 0):
					if (len(Paste.objects.filter(account = request.user.accountcontents , contents = '')) > 0):
						pasteObj.delete()
					return redirect('account')
				if (int(request.POST['public']) == 1):
					if (request.user.accountcontents.planType > 1):
						pasteObj.public = True
				else:
					pasteObj.public = False

				pasteObj.contents = str(request.POST['paste'])
				pasteObj.save()

				if ((Paste.objects.filter(account = request.user.accountcontents).count() < 100) and (len(Paste.objects.filter(account = request.user.accountcontents , contents = '')) == 0)):
					Paste.objects.create(account = request.user.accountcontents)
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Paste Not Saved.'})

			return redirect('account')

		elif ('url' in request.POST):
			if (request.user.accountcontents.planType == 1):
				if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 5):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
			elif (request.user.accountcontents.planType == 2):
				if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 15):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
			elif (request.user.accountcontents.planType == 3):
				if (ShortenedURL.objects.filter(account = request.user.accountcontents).count() >= 100):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of URLs allowed by your plan.'})
			else:
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You must have a plan to use this feature.'})

			try:
				validate = URLValidator()
				validate(str(request.POST['url']))
				ShortenedURL.objects.create(account = request.user.accountcontents , destinationURL = str(request.POST['url']))
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Invalid URL entered. You may have forgotten the "https://" at the beginning.'})

			return redirect('account')

		elif ('deleteURL' in request.POST):
			try:
				urlObj = ShortenedURL.objects.get(account = request.user.accountcontents , slug = str(request.POST['deleteURL']))
				urlObj.delete()
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})

			return redirect('account')

		elif ('recipientNumber' in request.POST):
			if (request.user.accountcontents.planType == 3):
				if (request.user.accountcontents.textsRemaining > 0):
					textForm = TextSendForm(request.POST)
					if (textForm.is_valid()):
						cd = textForm.cleaned_data
						toNumber = cd['recipientNumber']
						message = cd['message']
						messageLength = len(message)
						for char in message:
							if ((char == '\n') or (char == '\r')):
								messageLength += 1
						if (messageLength <= 140):
							validChars = '@ 0¡P¿p£_!1AQaq$Φ"2BRbr¥Γ\#3CScsèΛ¤4DTdtéΩ%5EUeuùΠ&6FVfvìΨ\'7GWgwòΣ(8HXhxÇΘ)9IYiy\n\rΞ*:JZjzØ+;KÄkäøÆ,<LÖlöæ-=MÑmñÅß.>NÜnüåÉ/?O§oà'
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
					return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. You Do Not Have Any Sends Left.'})

			return render(request , 'fullscreenMessage.html' , {'delay' : 6 , 'redirectURL' : reverse('account') , 'title' : 'Text Not Sent' , 'message' : 'Error. You probably used invalid characters. Note: emojis are not supported.'})

		elif ('recipient' in request.POST):
			fromAddress = ''
			if (request.user.accountcontents.planType == 3):
				if (str(request.POST['sender']) != 'Burner'):
					try:
						fwdObj = EmailForwarder.objects.get(account = request.user.accountcontents , forwarder = str(request.POST['sender']))
						fromAddress = fwdObj.forwarder
					except:
						return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error. Unable to send from that address.'})
			if (request.user.accountcontents.emailsRemaining > 0):
				request.user.accountcontents.emailsRemaining -= 1
				request.user.accountcontents.save()

				if (len(fromAddress) == 0):
					fromAddress = ((str(uuid.uuid4()).replace('-' , ''))[0:10] + '@Burn.Priveasy.org')

				sendEmail.delay(request.POST['subject'] , request.POST['message'] , fromAddress , [request.POST['recipient']])
				return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! Your email has been sent!'})


			else:
				return render(request , 'fullscreenMessage.html' , {'delay' : 6 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Unable to send message. You have no sends remaining.'})

		elif ('forwarder' in request.POST):
			if (request.user.accountcontents.planType == 1):
				if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 3):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
			elif (request.user.accountcontents.planType == 2):
				if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 5):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
			elif (request.user.accountcontents.planType == 3):
				if (EmailForwarder.objects.filter(account = request.user.accountcontents).count() >= 25):
					return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You have reached the maximum number of forwarders allowed by your plan.'})
			else:
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'You must have a plan to use this feature.'})

			try:
				validate = EmailValidator()
				validate(str(request.POST['forwarder']))
				fwdObj = EmailForwarder.objects.create(account = request.user.accountcontents , forwardTo = str(request.POST['forwarder']))
				with open('/home/ubuntu/Priveasy/mainSite/templates/email/fwdEmailConfirm.html' , 'r') as fwdEmailConfirmText:
					emailText = ((fwdEmailConfirmText.read()).replace('~' , fwdObj.verifID)).replace('`' , request.user.first_name)
					sendEmail.delay('Email Forwarding Verification' , emailText , 'EmailVerification@NoReply.Priveasy.org' , [fwdObj.forwardTo] , subType = 'html')
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Invalid Email Entered'})

			return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! Check your inbox (or spam folder) for the verification email.'})

		elif ('token' in request.POST):
			try:
				forwarderObj = EmailForwarder.objects.get(account = request.user.accountcontents , verifID = str(request.POST['token']))
				forwarderObj.verified = True
				forwarderObj.save()
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! This forwarder will be activated within 15 minutes!'})
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Failed' , 'message' : 'Error. An invalid token was submitted. Please try again.'})

		elif ('deleteForwarder' in request.POST):
			try:
				forwarderObj = EmailForwarder.objects.get(account = request.user.accountcontents , forwarder = str(request.POST['deleteForwarder']))
				forwarderObj.delete()
			except:
				return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})

			return redirect('account')


		else:
			return redirect('account')

	else:
		return redirect('account')


@login_required
def purchase(request):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	if (request.method == 'GET'):
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.purchasePageViews += 1
		pageStatsObj.save()

		return render(request , 'purchase.html' , {})

	elif (request.method == 'POST'):
		try:
			stripe.api_key = settings.stripeAPIKey

			autoRenewExists = True
			try:
				contents = request.POST['autoRenew']
			except:
				autoRenewExists = False

			if ((autoRenewExists) and (request.POST['autoRenew'] == 'Cancel')):
				stripe.Customer.delete(request.user.accountcontents.stripeID)
				request.user.accountcontents.stripeID = ''
				request.user.accountcontents.autoRenew = False
				request.user.accountcontents.save()
				return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Success!'})
			else:
				if (request.user.accountcontents.planExpiration > (int(time.time()) + 2592000)):
					return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'Payment not processed. Please wait until there are less than 30 days left in your plan, before renewing it.'})
				if (request.user.accountcontents.planType == 0):
					if (int(request.POST['planType']) == 1):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 200 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 200 , currency = 'usd' , description = 'Priveasy.org Plan #1 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 2):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 1200 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 1200 , currency = 'usd' , description = 'Priveasy.org Plan #1 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 3):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 400 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 400 , currency = 'usd' , description = 'Priveasy.org Plan #2 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 4):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 2250 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 2250 , currency = 'usd' , description = 'Priveasy.org Plan #2 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 5):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 500 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 500 , currency = 'usd' , description = 'Priveasy.org Plan #3 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 6):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 2850 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 2850 , currency = 'usd' , description = 'Priveasy.org Plan #3 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})
				elif (request.user.accountcontents.planType == 1):
					if (int(request.POST['planType']) == 1):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 200 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 200 , currency = 'usd' , description = 'Priveasy.org Plan #1 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 2):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 1200 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 1200 , currency = 'usd' , description = 'Priveasy.org Plan #1 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 1
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})
				elif (request.user.accountcontents.planType == 2):
					if (int(request.POST['planType']) == 1):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 400 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 400 , currency = 'usd' , description = 'Priveasy.org Plan #2 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 2):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 2250 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 2250 , currency = 'usd' , description = 'Priveasy.org Plan #2 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 2
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})
				elif (request.user.accountcontents.planType == 3):
					if (int(request.POST['planType']) == 1):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = False
							charge = stripe.Charge.create(amount = 500 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 500 , currency = 'usd' , description = 'Priveasy.org Plan #3 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = False
							request.user.accountcontents.save()
					elif (int(request.POST['planType']) == 2):
						if ((autoRenewExists) and (request.POST['autoRenew'] == 'Yes')):
							if (len(request.user.accountcontents.stripeID) == 0):
								customer = stripe.Customer.create(source = request.POST['stripeToken'] , email = request.user.email , )
							request.user.accountcontents.stripeID = customer.id
							request.user.accountcontents.autoRenew = True
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = True
							charge = stripe.Charge.create(amount = 2850 , currency = 'usd' , customer = customer.id , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )
							request.user.accountcontents.save()
						else:
							charge = stripe.Charge.create(amount = 2850 , currency = 'usd' , description = 'Priveasy.org Plan #3 Purchase' , source = request.POST['stripeToken'] , statement_descriptor = 'PRIVEASY' , receipt_email = request.user.email , )
							request.user.accountcontents.planType = 3
							request.user.accountcontents.longRenew = True
							request.user.accountcontents.save()
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})
				else:
					return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})

			if ((request.user.accountcontents.planExpiration - int(time.time())) <= 0):
				if (request.user.accountcontents.longRenew):
					request.user.accountcontents.planExpiration = int((time.time() + 15552000))
				else:
					request.user.accountcontents.planExpiration = int((time.time() + 2592000))
			else:
				if (request.user.accountcontents.longRenew):
					request.user.accountcontents.planExpiration += 15552000
				else:
					request.user.accountcontents.planExpiration += 2592000

			if (request.user.accountcontents.planType == 1):
				request.user.accountcontents.emailsRemaining = 0
				request.user.accountcontents.textsRemaining = 0
				for profile in VPNProfile.objects.filter(account = request.user.accountcontents):
					profile.delete()
			if (request.user.accountcontents.planType == 2):
				if (request.user.accountcontents.longRenew):
					request.user.accountcontents.emailsRemaining = 60
					request.user.accountcontents.textsRemaining = 0
				else:
					request.user.accountcontents.emailsRemaining = 10
					request.user.accountcontents.textsRemaining = 0
				if (len(VPNProfile.objects.filter(account = request.user.accountcontents)) != 1):
					for profile in VPNProfile.objects.filter(account = request.user.accountcontents):
						profile.delete()
					availableProfiles = VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1))
					for profile in availableProfiles:
						if (profile.server.serverType == 1):
							profile.account = request.user.accountcontents
							profile.vpnProfileNum = 1
							profile.save()
							break
			if (request.user.accountcontents.planType == 3):
				if (request.user.accountcontents.longRenew):
					request.user.accountcontents.emailsRemaining = 600
					request.user.accountcontents.textsRemaining = 600
				else:
					request.user.accountcontents.emailsRemaining = 100
					request.user.accountcontents.textsRemaining = 100
				if (len(VPNProfile.objects.filter(account = request.user.accountcontents)) != 2):
					for profile in VPNProfile.objects.filter(account = request.user.accountcontents):
						profile.delete()
					availableProfiles = VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1))
					domCount = 0
					forCount = 0
					for profile in availableProfiles:
						if ((domCount == 1) and (forCount == 1)):
							break
						if ((profile.server.serverType == 1) and (domCount < 1)):
							domCount += 1
							profile.account = request.user.accountcontents
							profile.vpnProfileNum = domCount
							profile.save()
						if ((profile.server.serverType == 2) and (forCount < 1)):
							forCount += 1
							profile.account = request.user.accountcontents
							profile.vpnProfileNum = 2
							profile.save()

			request.user.accountcontents.save()

			if (not(request.POST['referral_code'] == '')):
				try:
					referralCodeObj = ReferralCode.objects.get(code = request.POST['referral_code'].lower())
					if (referralCodeObj.account.planType >= request.user.accountcontents.planType):
						if (referralCodeObj.account.planExpiration - int(time.time()) > 0):
							if (not request.user.accountcontents.refCodeUsed):
								referralCodeObj.account.planExpiration += 2592000
								referralCodeObj.account.save()
								sendEmail.delay('Priveasy Referral Code' , ('Hello,\nWe are just writing to let you know that someone successfully used your referral code. An extra thirty days has been added to your account for free. Enjoy!\nIf you would like to get even more time for free, make sure to keep sharing your referral code (' + referralCodeObj.code + ') with others!\nThank you,\nPriveasy.org') , 'Referrals@NoReply.Priveasy.org' , [referralCodeObj.account.user.email] , standardNotificationTemplate = True)
								request.user.accountcontents.planExpiration += 2592000
								request.user.accountcontents.refCodeUsed = True
								request.user.accountcontents.save()
								sendEmail.delay('Priveasy Referral Code' , ('Hello,\nWe are just writing to let you know that you have successfully redeemed ' + referralCodeObj.account.user.first_name + '\'s referral code. An extra 30 days has been added to your account for free. Enjoy!\nIf you would like to get even more time for free, make sure to share your own referral code with others!\nThank you,\nPriveasy.org') , 'Referrals@NoReply.Priveasy.org' , [request.user.email] , standardNotificationTemplate = True)
							else:
								return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Thank you! Your payment processed successfully, although you have already used a referral code with this account, so the referral code was not applied.'})
						else:
							return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Thank you! Your payment processed successfully, although the account associated with the referral code you used is no longer active, so the code was not applied.'})
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 10 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Thank you! Your payment processed successfully, although the referral code could not be applied, as the account from which it came has a lower plan than yours.'})

				except:
					try:
						discountObj = Discount.objects.get(code = request.POST['referral_code'].lower())
						discountObj.timesUsed += 1
						discountObj.save()
						request.user.accountcontents.planExpiration += discountObj.timeAdded
						request.user.accountcontents.save()
						sendEmail.delay('Priveasy Discount Code' , discountObj.message , 'Discounts@NoReply.Priveasy.org' , [request.user.email] , standardNotificationTemplate = True)
						return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Thank you! Your payment processed successfully, and the discount code was applied'})
					except:
						return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Thank you! Your payment processed successfully, although an invalid code was used.'})

			return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('purchase') , 'title' : 'Success' , 'message' : 'Success! Thank you!'})

		except:
			return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('purchase') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})

	else:
		return redirect('purchase')


@login_required
def cryptoPayment(request):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	pageStatsObj = Stats.objects.get(id = 1)
	pageStatsObj.cryptoPageViews += 1
	pageStatsObj.save()

	try:
		zcashAddrObj = ZcashPaymentAddresses.objects.filter(account = request.user.accountcontents)[0]

		generated = False
		zAddr = ''
		tAddr = ''
		spotPrice = 0.0
		daysLeft = 180
		sendAmountUSD = 0.0
		sendAmountZEC = 0.0
		if (zcashAddrObj.requested):
			if (zcashAddrObj.generated):
				generated = True
				zAddr = zcashAddrObj.shieldedAddress
				tAddr = zcashAddrObj.transparentAddress

				try:
					spotPrice = float(requests.get('https://api.coinbase.com/v2/prices/ZEC-USD/spot').json()['data']['amount'])
				except:
					spotPrice = 50.0

				planExpiration = (request.user.accountcontents.planExpiration - int(time.time()))
				daysLeft = round(((planExpiration / 60) / 60) / 24)

				sendAmountUSD = (int(((180 - daysLeft) * (4.75 / 30)) * 100) / 100)

				sendAmountZEC = (int((sendAmountUSD / spotPrice) * 100000000) / 100000000)
		else:
			zcashAddrObj.requested = True
			zcashAddrObj.save()

		return render(request , 'cryptoPayment.html' , {'hasBeenGenerated' : generated , 'zAddress' : zAddr , 'tAddress' : tAddr , 'spotPrice' : spotPrice , 'daysLeft' : daysLeft , 'sendAmountUSD' : sendAmountUSD , 'sendAmountZEC' : sendAmountZEC})
	except:
		return render(request , 'fullscreenMessage.html' , {'delay' : 5 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again or contact support.'})


@login_required
def vpnDownload(request , slug = ''):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	if (request.method == 'GET'):
		try:
			if (request.user.accountcontents.planType == 2):
				if (len(slug) == 1):
					if (slug == '0'):
						emailContents = ''
						with open('/home/ubuntu/Priveasy/mainSite/templates/email/vpnEmail.html' , 'r') as emailFile:
							emailContents = emailFile.read()
						sendEmail.delay('VPN Installation Instructions' , emailContents , 'VPN@NoReply.Priveasy.org' , [request.user.email] , attach = False , attachments = [] , runCommandFirst = False , command = '' , subType = 'html')
						return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! The email has been sent!'})
					elif (slug == '1'):
						return render(request , 'vpnSelection.html' , {'slug1' : (slug + 'a') , 'slug2' : (slug + 'b') , 'slug3' : (slug + 'c') , 'slug4' : (slug + 'd') , 'slug5' : (slug + 'e') , 'slug6' : (slug + 'f') , 'slug7' : (slug + 'g') , 'slug8' : (slug + 'h') , 'slug9' : (slug + 'i') , 'slug10' : (slug + 'j')})
					elif (slug == '2'):
						return render(request , 'vpnSelection.html' , {'slug1' : (slug + 'a') , 'slug2' : (slug + 'b') , 'slug3' : (slug + 'c') , 'slug4' : (slug + 'd') , 'slug5' : (slug + 'e') , 'slug6' : (slug + 'f') , 'slug7' : (slug + 'g') , 'slug8' : (slug + 'h') , 'slug9' : (slug + 'i') , 'slug10' : (slug + 'j')})
					elif (slug == '3'):
						return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error! You must have plan #3 to use our Shadowsocks proxy.'})
				else:
					if (slug == '1a'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom1.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1b'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom2.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2a'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom1.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2b'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom2.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error! The URL you entered was invalid.'})
			if (request.user.accountcontents.planType == 3):
				if (len(slug) == 1):
					if (slug == '0'):
						emailContents = ''
						with open('/home/ubuntu/Priveasy/mainSite/templates/email/vpnEmail.html' , 'r') as emailFile:
							emailContents = emailFile.read()
						sendEmail.delay('VPN Installation Instructions' , emailContents , 'VPN@NoReply.Priveasy.org' , [request.user.email] , attach = False , attachments = [] , runCommandFirst = False , command = '' , subType = 'html')
						return render(request , 'fullscreenMessage.html' , {'delay' : 3 , 'redirectURL' : reverse('account') , 'title' : 'Success' , 'message' : 'Success! The email has been sent!'})
					elif (slug == '1'):
						return render(request , 'vpnSelection.html' , {'slug1' : (slug + 'a') , 'slug2' : (slug + 'b') , 'slug3' : (slug + 'c') , 'slug4' : (slug + 'd') , 'slug5' : (slug + 'e') , 'slug6' : (slug + 'f') , 'slug7' : (slug + 'g') , 'slug8' : (slug + 'h') , 'slug9' : (slug + 'i') , 'slug10' : (slug + 'j')})
					elif (slug == '2'):
						return render(request , 'vpnSelection.html' , {'slug1' : (slug + 'a') , 'slug2' : (slug + 'b') , 'slug3' : (slug + 'c') , 'slug4' : (slug + 'd') , 'slug5' : (slug + 'e') , 'slug6' : (slug + 'f') , 'slug7' : (slug + 'g') , 'slug8' : (slug + 'h') , 'slug9' : (slug + 'i') , 'slug10' : (slug + 'j')})
					elif (slug == '3'):
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
					if (slug == '1a'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom1.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1b'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom2.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1c'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-3.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom3.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1d'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-4.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom4.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1e'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-5.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom5.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1f'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff1.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1g'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff2.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1h'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-3.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff3.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1i'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-4.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff4.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '1j'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-5.conf') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff5.conf')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2a'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom1.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2b'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom2.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2c'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-3.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom3.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2d'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-4.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom4.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2e'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 1)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-5.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNdom5.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2f'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-1.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff1.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2g'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-2.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff2.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2h'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-3.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff3.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2i'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-4.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff4.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					elif (slug == '2j'):
						ioObj = BytesIO()
						profileObj = VPNProfile.objects.filter(account = request.user.accountcontents , vpnProfileNum = 2)
						profileObj = profileObj[0]
						with open(('/home/ubuntu/priveasyVPN/configs/' + profileObj.server.serverID + '/WireGuard/' + profileObj.vpnUsername + '-5.mobileconfig') , 'rb') as file:
							ioObj.write(file.read())
						response = HttpResponse(ioObj.getvalue() , content_type = 'application/xml')
						response['Content-Disposition'] = ('attachment; filename=PriveasyVPNoff5.mobileconfig')
						pageStatsObj = Stats.objects.get(id = 1)
						pageStatsObj.vpnDownloads += 1
						pageStatsObj.save()
						return response
					else:
						return render(request , 'fullscreenMessage.html' , {'delay' : 7 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'Error! The URL you entered was invalid.'})
		except:
			return render(request , 'fullscreenMessage.html' , {'delay' : 15 , 'redirectURL' : reverse('account') , 'title' : 'Maintenance' , 'message' : 'Server maintenance is currently being done. Please try again in a few hours. If this message persists for more than 24 hours, please contact support.'})
		return render(request , 'fullscreenMessage.html' , {'delay' : 4 , 'redirectURL' : reverse('account') , 'title' : 'Error' , 'message' : 'An error occurred. Please try again.'})
	else:
		return redirect('account')


def pastes(request , slug = ''):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	try:
		paste = Paste.objects.get(pasteID = slug , public = True)
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.publicPasteViews += 1
		pageStatsObj.save()
		return HttpResponse(str(paste.contents))
	except:
		return HttpResponse('No paste found at this URL.')


def policies(request , slug = ''):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
                return p5vcNotFound()

	if (slug == '1'):
		pageStatsObj = Stats.objects.get(id = 1)
                pageStatsObj.privacyPolicyViews += 1
                pageStatsObj.save()
		return render(request , 'policies/PrivacyPolicy.html' , {})
	elif (slug == '2'):
		pageStatsObj = Stats.objects.get(id = 1)
                pageStatsObj.termsViews += 1
                pageStatsObj.save()
		return render(request , 'policies/TermsOfService.html' , {})
	else:
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.priveasy404Views += 1
		pageStatsObj.save()
		raise Http404("Page does not exist")


def short(request , slug = ''):
	if (request.META['HTTP_HOST'] == 'p5.vc'):
		try:
			urlObj = ShortenedURL.objects.get(slug = slug)
			urlObj.clicks += 1
			urlObj.save()

			pageStatsObj = Stats.objects.get(id = 1)
			pageStatsObj.shortenedURLClicks += 1
			pageStatsObj.save()

			return redirect(urlObj.destinationURL , permanent = True)
		except:
			if (len(slug) == 6):
				return HttpResponse('This URL does not exist. Please make sure you typed the correct URL. It is also possible that the user who created this URL has since deleted it.')
			else:
				return p5vcNotFound()
	else:
		pageStatsObj = Stats.objects.get(id = 1)
		pageStatsObj.priveasy404Views += 1
		pageStatsObj.save()
		raise Http404("Page does not exist")
