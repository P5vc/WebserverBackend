from django.urls import path
from django.contrib.auth import views as authViews
from . import views

urlpatterns = [
				path('' , views.home , name = 'home'),
				path('account/' , views.account , name = 'account'),
				path('register/' , views.register , name = 'register'),
				path('paste/<slug:slug>/' , views.pastes , name = 'pastes'),
				path('logout/' , authViews.LogoutView.as_view() , name = 'logout'),
				path('change/password/' , authViews.PasswordChangeView.as_view(), name = 'password_change'),
				path('change/password/done/' , authViews.PasswordChangeDoneView.as_view() , name = 'password_change_done'),
				path('password/reset/' , authViews.PasswordResetView.as_view() , name = 'password_reset'),
				path('password/reset/done/' , authViews.PasswordResetDoneView.as_view() , name = 'password_reset_done'),
				path('password/reset/link/<uidb64>/<token>/' , authViews.PasswordResetConfirmView.as_view() , name = 'password_reset_confirm'),
				path('password/reset/confirm/done/' , authViews.PasswordResetCompleteView.as_view() , name = 'password_reset_complete'),
				path('account/purchase/' , views.purchase , name = 'purchase'),
				path('account/purchase/crypto/' , views.cryptoPayment , name = 'cryptoPayment'),
				path('vpn/download/<slug:slug>/' , views.vpnDownload , name = 'vpnDownload'),
				path('policies/<slug:slug>/' , views.policies , name = 'policies'),
				path('config/<slug:slug>' , views.config , name = 'config'),
				path('verify/<slug:slug>' , views.verify , name = 'verify'),
				path('<slug:slug>/' , views.short , name = 'short')
			]
