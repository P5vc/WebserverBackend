from django.db import models
from django.conf import settings
import uuid

class Stats(models.Model):
	# Page View Stats:
	homeViews = models.IntegerField('Number of times the home page was viewed' , default = 0)
	accountViews = models.IntegerField('Number of times an account page was viewed' , default = 0)
	termsViews = models.IntegerField('Number of times the Terms were viewed' , default = 0)
	privacyPolicyViews = models.IntegerField('Number of times the Privacy Policy was viewed' , default = 0)
	cryptoPageViews = models.IntegerField('Number of times the cryptocurrency purchase page was viewed' , default = 0)
	purchasePageViews = models.IntegerField('Number of times the purchase page was viewed' , default = 0)
	publicPasteViews = models.IntegerField('Number of times a public paste was successfully viewed' , default = 0)
	shortenedURLClicks = models.IntegerField('Number of times a shortened URL was clicked' , default = 0)
	vpnDownloads = models.IntegerField('Number of times a VPN profile was downloaded' , default = 0)
	shadowsocksViews = models.IntegerField('Number of times shadowsocks connection info was viewed' , default = 0)
	priveasy404Views = models.IntegerField('Number of times a 404 page was intentionally displayed for Priveasy.org' , default = 0)
	p5vc404Views = models.IntegerField('Number of times a 404 page was intentionally displayed for P5.vc' , default = 0)



class AccountContents(models.Model):
	def genSecret():
		return str(uuid.uuid4())


	user = models.OneToOneField(settings.AUTH_USER_MODEL , on_delete = models.CASCADE)

	# Account Data:
	accountCreated = models.DateTimeField('Account created' , auto_now_add = True)
	accountLastUpdated = models.DateTimeField('Account last updated' , auto_now = True)
	accountSecret = models.CharField('Account secret' , max_length = 36 , default = genSecret) # To be transmitted to the user via an external method, and used for action verifications
	emailVerified = models.BooleanField('Account email verified' , default = False)

	# Plan Data:
	planType = models.IntegerField('Plan number' , default = 0)
	planExpiration = models.IntegerField('Plan expiration' , default = 0)

	# Payment Data:
	autoRenew = models.BooleanField('Auto renew enabled' , default = False)
	longRenew = models.BooleanField('Renew for six months' , default = False)
	stripeID = models.CharField('Stripe customer ID' , max_length = 36 , blank = True)

	# Restrict Email Sends:
	emailsRemaining = models.IntegerField('Emails remaining' , default = 0)

	# Restrict Text Sends:
	textsRemaining = models.IntegerField('Texts remaining' , default = 0)

	# Restrict Referral Code Use:
	refCodeUsed = models.BooleanField('A referral code has been used' , default = False)

	# VPN Data:
	vpnPersistence = models.BooleanField('VPN profile persists through server upgrades' , default = False)



class VPNServer(models.Model):
	# Generate and return unique VPN server ID:
	def createServerID():
		while (True):
			id = ('server' + str(uuid.uuid4()).replace('-' , ''))[0:14]
			try:
				VPNServer.objects.get(serverID = id)
				continue
			except:
				return id


	serverID = models.CharField('Server ID' , max_length = 14 , default = createServerID)
	# For server type, 1 = Domestic and 2 = Offshore
	serverType = models.IntegerField('Server type' , default = 0)
	serverIP = models.GenericIPAddressField('Server IP address')



class VPNProfile(models.Model):
	server = models.ForeignKey(VPNServer , null = True , on_delete = models.CASCADE)
	account = models.ForeignKey(AccountContents , on_delete = models.CASCADE)

	# Generate and return unique VPN profile usernames:
	def createUsername():
		while (True):
			username = ('user' + str(uuid.uuid4()).replace('-' , ''))[0:14]
			try:
				VPNProfile.objects.get(vpnUsername = username)
				continue
			except:
				return username


	# Return the default VPN server:
	def returnDefaultServer():
		serverObj = VPNServer.objects.get(id = 1)
		return serverObj


	vpnUsername = models.CharField('VPN username' , max_length = 14 , default = createUsername)
	vpnProfileNum = models.IntegerField('VPN profile number' , default = 0)



class Paste(models.Model):
	account = models.ForeignKey(AccountContents , on_delete = models.CASCADE)

	# Generate and return unique paste ID:
	def createPasteID():
		while (True):
			tempPasteID = ((str(uuid.uuid4())).replace('-' , ''))[0:10]
			try:
				Paste.objects.get(pasteID = tempPasteID)
				continue
			except:
				return tempPasteID


	pasteID = models.CharField('Paste ID' , max_length = 10 , default = createPasteID)
	public = models.BooleanField('Paste is public' , default = False)
	# Allow 1MB per paste:
	contents = models.TextField('Paste contents' , max_length = 1000000 , blank = True)



class EmailForwarder(models.Model):
	account = models.ForeignKey(AccountContents , on_delete = models.CASCADE)

	def generateForwarder():
		while (True):
			email = (((str(uuid.uuid4()).replace('-' , ''))[0:8]) + '@fwd.priveasy.org')
			try:
				EmailForwarder.objects.get(fowarder = email)
				continue
			except:
				return email


	def createVerifID():
		return str(uuid.uuid4())


	verified = models.BooleanField('Email has been verified' , default = False)
	verifID = models.CharField('Verification String' , max_length = 36 , default = createVerifID)

	forwarder = models.EmailField('Email forwarder' , default = generateForwarder)
	forwardTo = models.EmailField('Forward to' , blank = True)



class ShortenedURL(models.Model):
	account = models.ForeignKey(AccountContents , on_delete = models.CASCADE)

	def generateURL():
		while (True):
			url = ((str(uuid.uuid4())).replace('-' , ''))[0:6]
			try:
				ShortenedURL.objects.get(slug = url)
				continue
			except:
				return url


	destinationURL = models.URLField('Destination URL' , max_length = 2000)
	slug = models.CharField('URL slug' , max_length = 6 , default = generateURL)
	clicks = models.IntegerField('Number of clicks' , default = 0)



class ReferralCode(models.Model):
	account = models.OneToOneField(AccountContents , on_delete = models.CASCADE)

	# Generate and return a unique referral code:
	def createReferralCode():
		while (True):
			tempCode = ((str(uuid.uuid4()).replace('-' , ''))[0:12])
			try:
				ReferralCode.objects.get(code = tempCode)
				continue
			except:
				return tempCode


	code = models.CharField('Referral code' , max_length = 12 , default = createReferralCode)



class ZcashPaymentAddresses(models.Model):
	account = models.OneToOneField(AccountContents , on_delete = models.CASCADE)

	requested = models.BooleanField('Addresses Requested' , default = False)
	generated = models.BooleanField('Addresses Generated' , default = False)

	shieldedAddress = models.CharField('Zcash Shielded Payment Address' , max_length = 100 , blank = True)
	transparentAddress = models.CharField('Zcash Transparent Payment Address' , max_length = 50 , blank = True)



class Discount(models.Model):
	# Generate and return a unique referral code:
	def createCouponCode():
		while (True):
			tempCode = ((str(uuid.uuid4()).replace('-' , ''))[0:10])
			try:
				Discount.objects.get(code = tempCode)
				continue
			except:
				return tempCode


	# Make sure the code, if manually entered, is lowercase
	code = models.CharField('Discount code' , max_length = 64 , default = createCouponCode)
	message = models.TextField('Emailed success message' , max_length = 10000 , default = 'Hello,\nThank you so much for using a discount code at checkout! We\'re just sending you this quick email to let you know that it was successfully applied. Have a nice day!\n- Priveasy\'s Friendly Server Bot')
	timeAdded = models.IntegerField('Amount of time to add to current plan' , default = 0)
	expiration = models.IntegerField('Discount code expiration' , default = 0)
	timesUsed = models.IntegerField('Number of times used' , default = 0)



# A model designed to send emails to users; objects will never be saved to database:
class EmailUsers(models.Model):
	sendTo = models.CharField('Recipient (if more than one, separate with a single space)' , max_length = 500 , default = 'Admin@Priveasy.org')

	sentFrom = models.CharField('Email address to send from' , max_length = 500 , default = 'Server@NoReply.Priveasy.org')

	subject = models.CharField('Email subject' , max_length = 500 , default = 'An Email From Priveasy')

	message = models.TextField('Email Message' , max_length = 10000 , default = 'Hello,\nI just wanted to reach out and quickly say thank you for using Priveasy! I really appreciate you!\n- Priveasy\'s Friendly Server Bot' , blank = True)

	standardNotificationTemplate = models.BooleanField('Use standard, HTML, notification template' , default = False)

	autoBCC = models.BooleanField('Automatically BCC multiple "to" addresses' , default = True)

	sendToVPNUsers = models.BooleanField('Automatically send email to all VPN users' , default = False)

	sendToAllUsers = models.BooleanField('Automatically send email to all users' , default = False)


	# Define custom save bahavior as to not touch the database:
	def save(self, *args, **kwargs):
		from .tasks import sendEmail
		sendEmail.delay(self.subject , self.message , self.sentFrom , self.sendTo.split() , standardNotificationTemplate = self.standardNotificationTemplate , autoBCC = self.autoBCC , sendToVPNUsers = self.sendToVPNUsers , sendToAllUsers = self.sendToAllUsers)
