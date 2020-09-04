from django.core.mail import EmailMessage
from django.contrib.auth.models import User
from django.conf import settings
from celery.decorators import task , periodic_task
from celery.task.schedules import crontab
import kronos , stripe
from twilio.rest import Client
from .models import *
from math import ceil as roundUp
from math import floor as roundDown
import subprocess , time , shutil , random , os , json , requests , pickle


@task(name = 'sendEmail')
def sendEmail(subject , message , sentFrom , sendTo , attach = False , attachments = [] , subType = 'plain' , standardNotificationTemplate = False , autoBCC = True , sendToVPNUsers = False , sendToAllUsers = False):
	subject = str(subject)
	sentFrom = str(sentFrom)
	sendTo = list(sendTo)
	message = str(message)

	if (sendToVPNUsers or sendToAllUsers):
		sendToList = []
		userObjsList = User.objects.all()
		for user in userObjsList:
			if (sendToAllUsers):
				sendToList.append(user.email)
				continue
			if (sendToVPNUsers and (not(sendToAllUsers))):
				if ((user.accountcontents.planType == 2) or (user.accountcontents.planType == 3)):
					sendToList.append(user.email)
		sendTo = sendToList

	if (standardNotificationTemplate):
		with open('/home/ubuntu/Priveasy/mainSite/templates/email/standardNotification.html' , 'r') as standardNotificationText:
			message = ((standardNotificationText.read()).replace('{EmailSubject}' , subject)).replace('{EmailBody}' , str(message))

	if (autoBCC and (len(sendTo) > 1)):
		email = EmailMessage(subject , message , sentFrom , [] , sendTo)
	else:
		email = EmailMessage(subject , message , sentFrom , sendTo)

	email.content_subtype = subType
	if (standardNotificationTemplate):
		email.content_subtype = 'html'
	if (attach):
		for attachment in attachments:
			email.attach_file(attachment)

	email.send()


@task(name = 'sendText')
def sendText(number , message):
	client = Client(settings.TWILIO_ACCOUNT_SID , settings.TWILIO_AUTH_TOKEN)
	client.messages.create(to = number , from_ = '+13364398765' , body = message)


@periodic_task(run_every = (crontab(minute='*/15')) , name = 'postmap' , ignore_result = True)
def postmap():
	with open('/etc/postfix/virtual' , 'w') as forwarderFile:
		contents = 'admin@fwd.priveasy.org Admin@Priveasy.org\nsupport@fwd.priveasy.org Support@Priveasy.org'
		for forwarder in (EmailForwarder.objects.filter(verified = True)):
			contents += ('\n' + forwarder.forwarder + ' ' + forwarder.forwardTo)
		forwarderFile.write(contents)
	subprocess.call('sudo postmap /etc/postfix/virtual' , shell = True)


# Handle all Zcash payments, address requests, etc.
@kronos.register('30 */3 * * *')
def zcash():
	def getLoadableResults(result):
		result = result.splitlines()
		parsedResults = []
		tempResult = ''
		for line in result:
			if ((((line == '') or (line[0] == '{')) or (line[0] == '[')) or (line[0] == ' ')):
				tempResult += line
			elif ((line[0] == '}') or (line[0] == ']')):
				tempResult += line
				parsedResults.append(json.loads(tempResult))
				tempResult = ''
			else:
				continue
		return parsedResults


	def addToAccount(amountInZatoshi , accountObj):
		try:
			spotPrice = float(requests.get('https://api.coinbase.com/v2/prices/ZEC-USD/spot').json()['data']['amount'])
		except:
			spotPrice = 50.0

		pricePerMonth = 4.75

		amountInUSD = ((amountInZatoshi * 0.00000001) * spotPrice)
		# Automatically apply 5% discount off of plan 3:
		monthsPaidFor = (amountInUSD / pricePerMonth)
		# Enforce 6-month restriction:
		if (monthsPaidFor > 6):
			monthsPaidFor = 6
		secondsPaidFor = int(monthsPaidFor * 2592000)

		if (accountObj.planType == 3):
			# Enforce 6-month restriction:
			if ((accountObj.planExpiration + secondsPaidFor) > (time.time() + 15552000)):
				accountObj.planExpiration = int(time.time() + 15552000)
			else:
				if ((time.time() - accountObj.planExpiration) > 0):
					accountObj.planExpiration = int(time.time() + secondsPaidFor)
				else:
					accountObj.planExpiration += secondsPaidFor
		else:
			accountObj.planType = 3
			accountObj.planExpiration = int(time.time() + secondsPaidFor)

		accountObj.emailsRemaining += int(100 * monthsPaidFor)
		accountObj.textsRemaining += int(100 * monthsPaidFor)
		if (accountObj.emailsRemaining > 600):
			accountObj.emailsRemaining = 600
		if (accountObj.textsRemaining):
			accountObj.textsRemaining = 600

		if (len(VPNProfile.objects.filter(account = accountObj)) != 2):
			for profile in VPNProfile.objects.filter(account = accountObj):
				profile.delete()

			availableProfiles = VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1))
			domCount = 0
			forCount = 0
			for profile in availableProfiles:
				if ((domCount == 1) and (forCount == 1)):
					break
				if ((profile.server.serverType == 1) and (domCount < 1)):
					domCount += 1
					profile.account = accountObj
					profile.vpnProfileNum = domCount
					profile.save()
				if ((profile.server.serverType == 2) and (forCount < 1)):
					forCount += 1
					profile.account = accountObj
					profile.vpnProfileNum = 2
					profile.save()

		accountObj.save()

		sendEmail.delay('Priveasy Payment Processed' , ('Hello,\n\nThis is just a quick email to let you know that your payment of ' + str(amountInZatoshi) + ' zatoshi has been successfully processed, and should now be reflected on your Priveasy account. The exchange rate at the time your payment was processed was ' + str(spotPrice) + 'USD per 1ZEC.\n\nThank you for using Zcash to pay for your plan. You are contributing to a better world, where privacy and security are key ideals, and we love to see it! Enjoy the added 5% discount for purchasing your plan with Zcash!\n\nIf you have any questions, don\'t hesitate to let us know!\n\n- Friendly Priveasy Server Bot') , 'ZcashPayment@NoReply.Priveasy.org' , [accountObj.user.email] , standardNotificationTemplate = True)


	for zcashAddrObj in ZcashPaymentAddresses.objects.filter(requested = True , generated = False):
		process = subprocess.Popen(['sudo' , '-u' , 'ubuntu' , '/home/ubuntu/Zcash/zecwallet-cli'] , stdout = subprocess.PIPE , stdin = subprocess.PIPE)
		command = (b'unlock ' + settings.ZCASH_WALLET_ENCRYPTION_KEY + b'\nnew z\n' + b'unlock ' + settings.ZCASH_WALLET_ENCRYPTION_KEY + b'\nnew t\n')
		process.stdin.write(command)
		process.stdin.flush()
		output = process.communicate()[0].decode()
		process.terminate()

		opener , unlock , newZ , unlock2 , newT , closer = getLoadableResults(output)

		if ((((opener['result'] == 'success') and (unlock['result'] == 'success')) and (unlock2['result'] == 'success')) and (closer['result'] == 'success')):
			zcashAddrObj.shieldedAddress = newZ[0]
			zcashAddrObj.transparentAddress = newT[0]
			zcashAddrObj.generated = True
			zcashAddrObj.save()
		else:
			sendEmail.delay('Urgent Priveasy Server Message' , 'An error ocurred while trying to generate new Zcash addresses. Please investigate the issue immediately.' , 'Server@NoReply.Priveasy.org' , ['Admin@Priveasy.org'] , standardNotificationTemplate = True)
			return

	# Handle any received payments:
	process = subprocess.Popen(['sudo' , '-u' , 'ubuntu' , '/home/ubuntu/Zcash/zecwallet-cli'] , stdout = subprocess.PIPE , stdin = subprocess.PIPE)
	command = (b'balance\n')
	process.stdin.write(command)
	process.stdin.flush()
	output = process.communicate()[0].decode()
	process.terminate()

	opener , balances , closer = getLoadableResults(output)

	if ((opener['result'] == 'success') and (closer['result'] == 'success')):
		totalBalance = -10000
		for address in balances['z_addresses']:
			if (address['verified_zbalance'] > 0):
				totalBalance += address['verified_zbalance']

				zcashAddressObj = ZcashPaymentAddresses.objects.filter(requested = True , generated = True , shieldedAddress = address['address'])[0]
				if (zcashAddressObj):
					addToAccount(address['verified_zbalance'] , zcashAddressObj.account)
		for address in balances['t_addresses']:
			if (address['balance'] > 0):
				totalBalance += address['balance']

				zcashAddressObj = ZcashPaymentAddresses.objects.filter(requested = True , generated = True , transparentAddress = address['address'])[0]
				if (zcashAddressObj):
					addToAccount(address['balance'] , zcashAddressObj.account)

		if (totalBalance > 0):
			process = subprocess.Popen(['sudo' , '-u' , 'ubuntu' , '/home/ubuntu/Zcash/zecwallet-cli'] , stdout = subprocess.PIPE , stdin = subprocess.PIPE)
			command = (b'unlock ' + settings.ZCASH_WALLET_ENCRYPTION_KEY + b'\nsend ' + settings.PRIVEASY_ZCASH_ADDRESS + b' ' + str(totalBalance).encode('utf-8') + b'\n')
			process.stdin.write(command)
			process.stdin.flush()
			output = process.communicate()[0].decode()
			process.terminate()

			opener , unlock , sendResult , closer = getLoadableResults(output)

			if (not('txid' in sendResult)):
				sendEmail.delay('Urgent Priveasy Server Message' , 'An error ocurred while trying to send a Zcash payment. Please investigate the issue immediately.' , 'Server@NoReply.Priveasy.org' , ['Admin@Priveasy.org'] , standardNotificationTemplate = True)
				return
	else:
		sendEmail.delay('Urgent Priveasy Server Message' , 'An error ocurred while trying to read current Zcash balances. Please investigate the issue immediately.' , 'Server@NoReply.Priveasy.org' , ['Admin@Priveasy.org'] , standardNotificationTemplate = True)
		return


# Automatically remove all VPN configuration files once a month:
@kronos.register('45 5 1 * *')
def cleanup():
	subprocess.call('rm -rf /home/ubuntu/priveasyVPN/configs/*' , shell = True)
	for server in VPNServer.objects.all():
		if (not (os.path.exists('/home/ubuntu/priveasyVPN/configs/' + server.serverID))):
			os.mkdir('/home/ubuntu/priveasyVPN/configs/' + server.serverID)


@kronos.register('0 0 * * *')
def maintenance():
	if (not(settings.SERVER_GENERATION == 'Base')):
		return

	stripe.api_key = settings.STRIPE_API_KEY

	userObjsList = User.objects.all()
	for user in userObjsList:
		secondsLeft = int(user.accountcontents.planExpiration - time.time())
		if (not(user.last_login)):
			user.last_login = user.date_joined
			user.save()
		secondsSinceLastLogin = int(time.time() - user.last_login.timestamp())

		if (((user.accountcontents.planType == 0) and (secondsLeft <= 0)) and (secondsSinceLastLogin > 2592000)):
			sendEmail.delay('Priveasy Account Deleted' , 'Your account at Priveasy.org has been removed. This is a normal process that occurs for security and privacy reasons, and to preserve server resources when accounts don\'t have an active plan and haven\'t been logged-into for over 30 days. We hope you\'ll come back soon, and you\'re always welcome to create a new account! Thank you, and sorry for the inconvenience!' , 'AccountRemoval@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)
			user.delete()
			continue

		if (((user.accountcontents.planType == 0) and (secondsLeft <= 0)) and (secondsSinceLastLogin > 2332800)):
			sendEmail.delay('Priveasy Account Removal' , 'Your account at Priveasy.org is scheduled to be removed in one week. This is a normal process that occurs for security and privacy reasons, and to preserve server resources when accounts don\'t have an active plan and haven\'t been logged-into for over 30 days. To cancel this removal, simply log into your account within one week\'s time. In the event that your account is removed, you\'re always welcome to create a new one at a later date! Thank you, and sorry for the inconvenience!' , 'AccountRemoval@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)

		if ((secondsLeft <= 0) and (user.accountcontents.planType > 0)):
			user.accountcontents.planType = 0
			user.accountcontents.autoRenew = False
			user.accountcontents.longRenew = False
			user.accountcontents.stripeID = ''
			user.accountcontents.emailsRemaining = 0
			user.accountcontents.textsRemaining = 0
			user.accountcontents.save()
			for vpnProfile in (VPNProfile.objects.filter(account = user.accountcontents)):
				vpnProfile.delete()
			for paste in (Paste.objects.filter(account = user.accountcontents)):
				paste.delete()
			for url in (ShortenedURL.objects.filter(account = user.accountcontents)):
				url.delete()
			for emailFWD in (EmailForwarder.objects.filter(account = user.accountcontents)):
				emailFWD.delete()

		if (user.accountcontents.planType == 0):
			continue

		if (user.accountcontents.autoRenew):
			if (secondsLeft <= 604800):
				try:
					if (user.accountcontents.planType == 1):
						if (user.accountcontents.longRenew):
							charge = stripe.Charge.create(amount = 1200 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
						else:
							charge = stripe.Charge.create(amount = 200 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #1 Purchase' , statement_descriptor = 'PRIVEASY' , )
					if (user.accountcontents.planType == 2):
						if (user.accountcontents.longRenew):
							charge = stripe.Charge.create(amount = 2250 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
						else:
							charge = stripe.Charge.create(amount = 400 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #2 Purchase' , statement_descriptor = 'PRIVEASY' , )
					if (user.accountcontents.planType == 3):
						if (user.accountcontents.longRenew):
							charge = stripe.Charge.create(amount = 2850 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )
						else:
							charge = stripe.Charge.create(amount = 500 , currency = 'usd' , customer = user.accountcontents.stripeID , description = 'Priveasy.org Plan #3 Purchase' , statement_descriptor = 'PRIVEASY' , )

					if (user.accountcontents.longRenew):
						user.accountcontents.planExpiration += 15552000
					else:
						user.accountcontents.planExpiration += 2592000

					if (user.accountcontents.planType == 1):
						user.accountcontents.emailsRemaining = 0
						user.accountcontents.textsRemaining = 0
					if (user.accountcontents.planType == 2):
						if (user.accountcontents.longRenew):
							user.accountcontents.emailsRemaining = 60
							user.accountcontents.textsRemaining = 0
						else:
							user.accountcontents.emailsRemaining = 10
							user.accountcontents.textsRemaining = 0
					if (user.accountcontents.planType == 3):
						if (user.accountcontents.longRenew):
							user.accountcontents.emailsRemaining = 600
							user.accountcontents.textsRemaining = 600
						else:
							user.accountcontents.emailsRemaining = 100
							user.accountcontents.textsRemaining = 100

					sendEmail.delay('Priveasy Plan Recharge' , 'Hello,\nThis is just a quick message letting you know that your Priveasy.org plan was successfully renewed today. If you wish to change your payment settings, feel free to login and visit your dashboard for the link to our payment page. Thank you very much for your patronage!' , 'AccountRenewal@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)

				except:
					sendEmail.delay('Priveasy Payment Error' , 'Hello,\nThis is just a quick message letting you know that your Priveasy.org plan could not be renewed today. It is likely that your payment settings are no longer valid. We recommend logging in to your account, visiting your dashboard, and then clicking on the link to bring you to our payment page. From there you can cancel the autorecharge feature and re-enter your credit card details. If you think that there is no issue with your payment details, take no action, and we will attempt to place the charge again once per day for a one week span following the incident. You will be notified of the success of each attempt.' , 'AccountRenewal@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)
		else:
			daysLeft = int(((secondsLeft / 60) / 60) / 24)
			if (daysLeft == 13):
				sendEmail.delay('Priveasy Plan Expiration' , 'This is just a friendly reminder that your current Priveasy.org plan will expire in two weeks. Feel free to login and visit your dashboard for the link to our payment page. From there you can choose to make a one-time payment to extend your plan, or enable autorecharge, and we\'ll automatically charge your card once your plan is almost up.' , 'ExpiryNotifications@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)
			if (daysLeft == 6):
				sendEmail.delay('Priveasy Plan Expiration' , 'This is just a friendly reminder that your current Priveasy.org plan will expire in one week. Feel free to login and visit your dashboard for the link to our payment page. From there you can choose to make a one-time payment to extend your plan, or enable autorecharge, and we\'ll automatically charge your card once your plan is almost up.' , 'ExpiryNotifications@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)
			if (daysLeft == 1):
				sendEmail.delay('Priveasy Plan Expiration' , 'This is just a friendly reminder that your current Priveasy.org plan will expire in two days. Feel free to login and visit your dashboard for the link to our payment page. From there you can choose to make a one-time payment to extend your plan, or enable autorecharge, and we\'ll automatically charge your card once your plan is almost up.' , 'ExpiryNotifications@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)
			if (daysLeft == 0):
				sendEmail.delay('Priveasy Plan Expiration' , 'This is just a friendly reminder that your current Priveasy.org plan will expire in less than one day. Feel free to login and visit your dashboard for the link to our payment page. From there you can choose to make a one-time payment to extend your plan, or enable autorecharge, and we\'ll automatically charge your card once your plan is almost up.' , 'ExpiryNotifications@NoReply.Priveasy.org' , [user.email] , standardNotificationTemplate = True)

		if ((user.accountcontents.planType == 2) and (user.username != 'admin')):
			if (len(VPNProfile.objects.filter(account = user.accountcontents)) != 1):
				for profile in VPNProfile.objects.filter(account = user.accountcontents):
					profile.delete()
				availableProfiles = VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1))
				for profile in availableProfiles:
					if (profile.server.serverType == 1):
						profile.account = user.accountcontents
						profile.vpnProfileNum = 1
						profile.save()
						break
		if ((user.accountcontents.planType == 3) and (user.username != 'admin')):
			if (len(VPNProfile.objects.filter(account = user.accountcontents)) != 2):
				for profile in VPNProfile.objects.filter(account = user.accountcontents):
					profile.delete()
				availableProfiles = VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1))
				domCount = 0
				forCount = 0
				for profile in availableProfiles:
					if ((domCount == 1) and (forCount == 1)):
						break
					if ((profile.server.serverType == 1) and (domCount < 1)):
						domCount += 1
						profile.account = user.accountcontents
						profile.vpnProfileNum = domCount
						profile.save()
					if ((profile.server.serverType == 2) and (forCount < 1)):
						forCount += 1
						profile.account = user.accountcontents
						profile.vpnProfileNum = 2
						profile.save()

	idealVPNProfilesNum = int((AccountContents.objects.filter(planType = 2).count() + (2 * AccountContents.objects.filter(planType = 3).count()) + 5) * 1.05)
	if ((idealVPNProfilesNum % 2) != 0):
		idealVPNProfilesNum += 1
	if (VPNProfile.objects.count() < idealVPNProfilesNum):
		for i in range(1 , (idealVPNProfilesNum - VPNProfile.objects.count()) + 1):
			if ((i % 2) == 0):
				serverList = VPNServer.objects.filter(serverType = 2)
				server = serverList[random.randint(0 , (len(serverList) - 1))]
				VPNProfile.objects.create(server = server , account = AccountContents.objects.get(id = 1))
			else:
				serverList = VPNServer.objects.filter(serverType = 1)
				server = serverList[random.randint(0 , (len(serverList) - 1))]
				VPNProfile.objects.create(server = server , account = AccountContents.objects.get(id = 1))
	while (VPNProfile.objects.count() > idealVPNProfilesNum):
		domCount = 0
		forCount = 0
		for profile in VPNProfile.objects.filter(account = AccountContents.objects.get(id = 1)):
			if ((domCount >= 1) and (forCount >= 1)):
				break
			if ((profile.server.serverType == 1) and (domCount < 1)):
				domCount += 1
				profile.delete()
			if ((profile.server.serverType == 2) and (forCount < 1)):
				forCount += 1
				profile.delete()

	for server in VPNServer.objects.all():
		with open('/home/ubuntu/priveasyVPN/' + server.serverID + '.conf' , 'w') as configFile:
			usernameList = ''
			for profile in VPNProfile.objects.filter(server = server):
				if (profile.account.vpnPersistence):
					usernameList += ('p' + profile.vpnUsername + '\n')
				else:
					usernameList += (profile.vpnUsername + '\n')
			configFile.write(usernameList)
		if (not (os.path.exists('/home/ubuntu/priveasyVPN/configs/' + server.serverID))):
			os.mkdir('/home/ubuntu/priveasyVPN/configs/' + server.serverID)
		if (not (os.path.exists('/home/ubuntu/priveasyVPN/configs/' + server.serverID + '/pUsers.dat'))):
			with open(('/home/ubuntu/priveasyVPN/configs/' + server.serverID + '/pUsers.dat') , 'w') as pUsersFile:
				pickle.dump({'WireGuard' : [] , 'Shadowsocks' : []} , pUsersFile)

	for discountObj in Discount.objects.all():
		if (time.time() >= discountObj.expiration):
			sendEmail.delay('Priveasy.org Server Message' , ('The discount code: "' + discountObj.code + '" has expired, and was deleted. This code was used a total of ' + str(discountObj.timesUsed) + ' times.') , 'Server@NoReply.Priveasy.org' , ['Admin@Priveasy.org'] , standardNotificationTemplate = True)
			discountObj.delete()

	diskUsage = shutil.disk_usage('/')
	sendEmail.delay('Priveasy.org Server Message' , 'This is the standard email sent once a day at the completion of the maintenance job. There are currently ' + str(len(userObjsList)) + ' users, ' + str(VPNProfile.objects.count()) + ' VPN profiles, ' + str(VPNServer.objects.filter(serverType = 2).count()) + ' foreign VPN servers, and ' + str(VPNServer.objects.filter(serverType = 1).count()) + ' domestic VPN servers. Currently the server has ' + str(int((diskUsage[0] / 1000000000) * 100) / 100) + 'GB of storage, of which ' + str(int(diskUsage[1] / diskUsage[0] * 10000) / 100) + '% is used.' , 'Server@NoReply.Priveasy.org' , ['Admin@Priveasy.org'] , standardNotificationTemplate = True)
