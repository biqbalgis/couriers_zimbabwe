from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
@admin.register(User)
class MarketplaceUserAdmin(UserAdmin):
    fieldsets=UserAdmin.fieldsets+(("Marketplace",{"fields":("name","phone","role","verified")}),)
    add_fieldsets=UserAdmin.add_fieldsets+(("Marketplace",{"fields":("name","phone","role","verified")}),)
    list_display=("username","name","phone","role","is_active","verified")
    list_filter=UserAdmin.list_filter+("role","verified")
class ReadOnlyWorkflowAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
for model in (OperationalCase,DeliveryAttempt,CustodyEvidence,AdminAudit,StatusEvent,FinanceEvent,Payment,Payout,Parcel,Task):
    admin.site.register(model,ReadOnlyWorkflowAdmin)
for model in (City,Station,Carrier,Rider,RateTableEntry,SupportTicket,Notification,Address,PlatformSettings,CarrierTrip): admin.site.register(model)
