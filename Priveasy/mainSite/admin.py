from django.contrib import admin
from .models import *

@admin.register(AccountContents)
class AccountContentsAdmin(admin.ModelAdmin):
	list_display = ['user' , 'planType']

@admin.register(Stats)
class StatsAdmin(admin.ModelAdmin):
	list_display = ['homeViews' , 'accountViews' , 'vpnDownloads']

@admin.register(VPNProfile)
class VPNProfileAdmin(admin.ModelAdmin):
	list_display = ['vpnUsername' , 'server' , 'vpnProfileNum' , 'persistent']

@admin.register(Paste)
class PasteAdmin(admin.ModelAdmin):
	list_display = ['pasteID' , 'public']

@admin.register(EmailForwarder)
class EmailForwarder(admin.ModelAdmin):
	list_display = ['forwarder' , 'forwardTo']

@admin.register(ShortenedURL)
class ShortenedURL(admin.ModelAdmin):
	list_display = ['slug' , 'destinationURL' , 'clicks']

@admin.register(ReferralCode)
class ReferralCode(admin.ModelAdmin):
	list_display = ['code']

@admin.register(VPNServer)
class VPNServer(admin.ModelAdmin):
	list_display = ['serverID' , 'serverIP' , 'serverType']

@admin.register(Discount)
class Discount(admin.ModelAdmin):
	list_display = ['code']

@admin.register(EmailUsers)
class EmailUsers(admin.ModelAdmin):
	pass

@admin.register(ZcashPaymentAddresses)
class ZcashPaymentAddresses(admin.ModelAdmin):
	list_display = ['requested' , 'generated' , 'account']
