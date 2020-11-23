def checkPermission(resourceID , user):
	'''
	Checks user permissions then returns True or False.

	This function accepts a resource ID and a user object, then determines if
	the supplied user has permission to access the resource indicated by the
	resource ID. If the user has the proper permissions, then True is returned.
	If not, then False is returned.

	Accepts:
		resourceID (str): Unique identifier of the resource to check
		permissions against

		user (django.contrib.auth.models.User): A Django user object

	Returns:
		(bool): Returns a boolean value of True or False
	'''

	if (resourceID == 'pastebin'):
		if (user.accountcontents.planType > 0):
			return True
	elif (resourceID == 'publicPaste'):
		if (user.accountcontents.planType > 1):
			return True

	elif (resourceID == 'urlShortener'):
		if (user.accountcontents.planType > 0):
			return True
	elif (resourceID == 'canHave5URLs'):
		if (user.accountcontents.planType >= 1):
			return True
	elif (resourceID == 'canHave15URLs'):
		if (user.accountcontents.planType >= 2):
			return True
	elif (resourceID == 'canHave100URLs'):
		if (user.accountcontents.planType >= 3):
			return True

	elif (resourceID == 'textMessaging'):
		if (user.accountcontents.planType >= 3):
			return True
	elif (resourceID == 'textsRemaining'):
		if (user.accountcontents.textsRemaining > 0):
			return True

	elif (resourceID == 'emailForwarder'):
		if (user.accountcontents.planType > 0):
			return True
	elif (resourceID == 'canHave3Forwarders'):
		if (user.accountcontents.planType >= 1):
			return True
	elif (resourceID == 'canHave5Forwarders'):
		if (user.accountcontents.planType >= 2):
			return True
	elif (resourceID == 'canHave25Forwarders'):
		if (user.accountcontents.planType >= 3):
			return True

	elif (resourceID == 'burnerEmail'):
		if (user.accountcontents.planType >= 2):
			return True
	elif (resourceID == 'emailsRemaining'):
		if (user.accountcontents.emailsRemaining > 0):
			return True
	elif (resourceID == 'sendFromForwarder'):
		if (user.accountcontents.planType >= 3):
			return True

	return False
