from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from .models import City,Notification,Parcel,RateTableEntry,Station,StatusEvent,User
from .services import create_parcel, lookup_rate, transition
from .workflows import issue_handover_code
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO

def receipt():
    data=BytesIO(); Image.new('RGB',(10,10),'white').save(data,format='PNG')
    return SimpleUploadedFile('receipt.png',data.getvalue(),content_type='image/png')
from django.core.management import call_command
from django.test import override_settings
from io import StringIO
from .models import Address,Carrier,Payment,Payout,Rider,SupportTicket,Task

@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'}})
class MarketplaceFlowTests(TestCase):
    def test_idempotent_retry_runs_operation_once_and_rejects_changed_payload(self):
        from .workflows import run_idempotent
        calls=[]
        def operation():
            calls.append(1); return {'accepted':True}
        for _ in range(2):
            self.assertEqual(run_idempotent(self.customer,'retry-key','/tasks/1/complete/',{'otp':'123456'},operation),{'accepted':True})
        self.assertEqual(len(calls),1)
        with self.assertRaises(ValidationError): run_idempotent(self.customer,'retry-key','/tasks/1/complete/',{'otp':'654321'},operation)

    def test_booking_and_onboarding_require_uploads(self):
        data={"recipient_name":"Recipient","recipient_phone":"+263771000099","origin_station":self.origin.pk,"destination_station":self.destination.pk,"weight_band":"0-2kg"}
        client=self.client_for(self.customer)
        response=client.post('/api/parcels/',data)
        self.assertEqual(response.status_code,400); self.assertIn('photo',response.data)
        self.assertEqual(client.post('/api/parcels/',{**data,'photo':receipt()},format='multipart').status_code,201)
        self.assertEqual(client.post('/api/parcels/',{**data,'weight_band':'unknown','photo':receipt()},format='multipart').status_code,400)
        rider_user=User.objects.create_user(username='applicant',phone='+263771000100',name='Applicant',role='rider')
        response=self.client_for(rider_user).post('/api/riders/',{'home_station':self.origin.pk})
        self.assertEqual(response.status_code,400); self.assertIn('document',response.data)
        profile=Rider.objects.create(user=rider_user,home_station=self.origin)
        self.assertEqual(self.client_for(self.ops).post(f'/api/onboarding/{profile.pk}/approve/',{'type':'rider'}).status_code,400)
        response=self.client_for(self.ops).post('/api/parcels/',{**data,'photo':receipt()},format='multipart')
        self.assertEqual(response.status_code,400); self.assertIn('customer',str(response.data).lower())

    def test_handover_codes_are_hashed_and_cannot_be_reset_while_active(self):
        from django.contrib.auth.hashers import check_password
        code=issue_handover_code(self.parcel,'at_origin_station',self.customer)['code']
        self.parcel.refresh_from_db()
        self.assertNotEqual(code,self.parcel.handover_otp)
        self.assertTrue(check_password(code,self.parcel.handover_otp))
        with self.assertRaises(ValidationError): issue_handover_code(self.parcel,'at_origin_station',self.customer)
        transition(self.parcel,self.ops,'at_origin_station',code)
        self.parcel.refresh_from_db(); self.assertEqual(self.parcel.handover_otp,'')

    def test_requested_pickup_cannot_be_skipped(self):
        self.parcel.pickup_address='Collect me'; self.parcel.save()
        with self.assertRaises(ValidationError): issue_handover_code(self.parcel,'at_origin_station',self.customer)

    @override_settings(DEBUG=True,SMS_DELIVERY_MODE='console')
    def test_sms_processing_synchronizes_notification_without_claiming_live_delivery(self):
        from .models import IntegrationDelivery
        from .integrations import deliver_one
        notification=Notification.objects.filter(parcel=self.parcel).first()
        item=IntegrationDelivery.objects.get(kind='sms',payload__notification_id=notification.pk)
        self.assertEqual(deliver_one(item.pk),'development')
        notification.refresh_from_db(); self.assertEqual(notification.status,'development'); self.assertIsNone(notification.sent_at)

    def test_after_hours_helpdesk_defers_create_reply_and_status(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from unittest.mock import patch
        from .workflows import queue_helpdesk
        from .services import reply_ticket,set_ticket_status
        from .models import IntegrationDelivery
        from .integrations import deliver_one
        ticket=SupportTicket.objects.create(raised_by=self.customer,subject='Help')
        now=datetime(2030,1,1,21,0,tzinfo=ZoneInfo('Africa/Harare'))
        with patch('marketplace.workflows.timezone.localtime',return_value=now):
            queue_helpdesk(ticket)
            reply_ticket(ticket,self.customer,'After-hours message')
            set_ticket_status(ticket,self.ops,'waiting_customer')
        items=IntegrationDelivery.objects.filter(kind='helpdesk')
        self.assertEqual(items.count(),3)
        for item in items:
            self.assertEqual(item.available_at.astimezone(ZoneInfo('Africa/Harare')).hour,8)
            self.assertEqual(deliver_one(item.pk),'deferred')
            item.refresh_from_db(); self.assertEqual(item.attempts,0)

    def test_two_rider_journey_settles_each_completed_leg(self):
        from .models import CarrierTrip
        from .services import assign_parcel,respond_task
        from django.utils import timezone
        from datetime import timedelta
        from .workflows import custody_transition
        pickup=User.objects.create_user(username='pickup',phone='+263771001001',name='Pickup rider',role='rider')
        delivery=User.objects.create_user(username='delivery',phone='+263771001002',name='Delivery rider',role='rider')
        carrier_user=User.objects.create_user(username='transport',phone='+263771001003',name='Carrier',role='carrier')
        destination_op=User.objects.create_user(username='destination',phone='+263771001004',name='Destination',role='station_operator')
        self.destination.operator=destination_op; self.destination.save()
        first=Rider.objects.create(user=pickup,home_station=self.origin,status='approved',available=True)
        last=Rider.objects.create(user=delivery,home_station=self.destination,status='approved',available=True)
        carrier=Carrier.objects.create(user=carrier_user,vehicle_type='Van',licence_no='LIC',capacity_kg=100,status='approved')
        trip=CarrierTrip.objects.create(carrier=carrier,origin_city=self.origin.city,destination_city=self.destination.city,departure_at=timezone.now()+timedelta(days=1),capacity_kg=100)
        self.parcel.pickup_address='Pickup'; self.parcel.delivery_choice='home'; self.parcel.delivery_address='Delivery'; self.parcel.save()
        Payment.objects.create(parcel=self.parcel,amount=self.parcel.price,status='verified',receipt_photo=receipt(),verified_at=timezone.now())
        assign_parcel(self.parcel,{'rider':first,'trip':trip})
        for task in self.parcel.tasks.all(): respond_task(task,task.assigned_to,True)
        def step(actor,target,confirmer=None,recipient=False,**proof):
            self.parcel.refresh_from_db()
            code=issue_handover_code(self.parcel,target,confirmer,recipient=recipient)['code']
            custody_transition(self.parcel,actor,target,code,**proof)
        step(pickup,'picked_up',self.customer)
        step(self.ops,'at_origin_station',pickup)
        step(carrier_user,'in_transit',self.ops)
        step(destination_op,'at_destination_station',carrier_user)
        self.parcel.refresh_from_db(); assign_parcel(self.parcel,{'rider':last})
        task=self.parcel.tasks.get(type='last_mile_delivery'); respond_task(task,delivery,True)
        step(delivery,'out_for_delivery',destination_op)
        step(delivery,'delivered',recipient=True,proof_photo=receipt(),signature=receipt())
        self.assertEqual(self.client_for(pickup).get(f'/api/parcels/{self.parcel.code}/').status_code,200)
        data={'parcel':self.parcel.pk,'period':'2026-10','first_mile_rider':'1','last_mile_rider':'2','carrier':'3','station':'1'}
        response=self.client_for(self.ops).post('/api/payouts/run/',data)
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(Payout.objects.get(leg='first_mile').beneficiary,pickup)
        self.assertEqual(Payout.objects.get(leg='last_mile').beneficiary,delivery)
        self.assertEqual(sum(Payout.objects.values_list('amount',flat=True)),self.parcel.price)
        self.assertEqual(self.client_for(self.ops).post('/api/payouts/run/',data).status_code,400)

    def setUp(self):
        self.customer=User.objects.create_user(username="customer",phone="0770000001",name="Customer",password="pass",role="customer")
        self.ops=User.objects.create_user(username="ops",phone="0770000002",name="Ops",password="pass",role="ops")
        a=City.objects.create(name="Harare",province="Harare"); b=City.objects.create(name="Bulawayo",province="Bulawayo")
        self.origin=Station.objects.create(name="A",city=a,address="A",operator=self.ops,payment_number="1")
        self.destination=Station.objects.create(name="B",city=b,address="B",operator=self.ops,payment_number="2")
        RateTableEntry.objects.create(origin_city=a,destination_city=b,weight_band="0-2kg",price=12)
        RateTableEntry.objects.create(origin_city=a,destination_city=b,weight_band="0-2kg",price=10,station_override=self.origin)
        self.parcel=create_parcel({"recipient_name":"Recipient","recipient_phone":"0771","origin_station":self.origin,"destination_station":self.destination,"weight_band":"0-2kg"},self.customer)
    def test_station_override_and_booking_notifications(self):
        self.assertEqual(lookup_rate(self.origin,self.destination,"0-2kg").price,10)
        self.assertEqual(self.parcel.price,10); self.assertEqual(Notification.objects.filter(parcel=self.parcel).count(),2)
    def test_global_search_respects_visibility_and_pagination(self):
        other=User.objects.create_user(username="outsider",phone="0770000099",name="Outside",role="customer")
        hidden=create_parcel({"recipient_name":"Hidden Needle","recipient_phone":"0772","origin_station":self.origin,"destination_station":self.destination,"weight_band":"0-2kg"},other)
        client=APIClient(); client.force_authenticate(self.customer)
        response=client.get("/api/parcels/",{"search":"Hidden Needle","page_size":1})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data["count"],0)
        client.force_authenticate(self.ops)
        response=client.get("/api/parcels/",{"search":"Hidden Needle","page_size":1})
        self.assertEqual(response.data["count"],1)
        self.assertEqual(response.data["results"][0]["code"],hidden.code)
    def test_human_readable_rate_and_payment_fields(self):
        client=APIClient(); client.force_authenticate(self.ops)
        response=client.get("/api/rates/",{"search":"Harare"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data["results"][0]["origin_name"],"Harare")
        self.assertEqual(response.data["results"][0]["destination_name"],"Bulawayo")
    def test_visible_next_steps_match_delivery_preference(self):
        from .serializers import ParcelSerializer
        self.assertEqual(ParcelSerializer(self.parcel).data["next_steps"],["at_origin_station"])
        self.parcel.status="at_destination_station"
        self.assertEqual(ParcelSerializer(self.parcel).data["next_steps"],["delivered"])
        self.parcel.delivery_choice="home"
        self.assertEqual(ParcelSerializer(self.parcel).data["next_steps"],["out_for_delivery"])
    def test_rejected_transition_is_logged_without_state_change(self):
        with self.assertRaises(ValidationError): transition(self.parcel,self.ops,Parcel.Status.IN_TRANSIT,"wrong")
        self.parcel.refresh_from_db(); self.assertEqual(self.parcel.status,Parcel.Status.BOOKED)
        self.assertTrue(StatusEvent.objects.filter(parcel=self.parcel,accepted=False,note__startswith="ALERT").exists())
    def test_valid_transition_and_append_only_guards(self):
        code=issue_handover_code(self.parcel,"at_origin_station",self.customer)["code"]
        transition(self.parcel,self.ops,Parcel.Status.AT_ORIGIN,code)
        self.parcel.refresh_from_db(); self.assertEqual(self.parcel.status,Parcel.Status.AT_ORIGIN)
        event=self.parcel.events.last(); event.note="changed"
        with self.assertRaises(DjangoValidationError): event.save()
        with self.assertRaises(DjangoValidationError): StatusEvent.objects.filter(pk=event.pk).delete()
    def test_public_tracking_excludes_sender_account(self):
        response=APIClient().get(f"/api/track/{self.parcel.recipient_access_token}/")
        self.assertEqual(response.status_code,200); self.assertNotIn("sender",response.data); self.assertNotIn("price",response.data)

    def client_for(self,user):
        client=APIClient(); client.force_authenticate(user); return client

    def test_profile_cannot_escalate_role(self):
        response=self.client_for(self.customer).patch('/api/users/me/',{"name":"Updated","role":"admin","phone":"+263771999999"})
        self.assertEqual(response.status_code,200)
        self.customer.refresh_from_db(); self.assertEqual(self.customer.role,"customer"); self.assertEqual(self.customer.name,"Updated")
        self.assertEqual(self.customer.phone,'0770000001')

    def test_only_admin_can_create_users(self):
        data={"username":"new","phone":"0770000003","name":"New","role":"finance","password":"Test12345!"}
        self.assertEqual(self.client_for(self.ops).post('/api/users/',data).status_code,403)
        admin=User.objects.create_user(username="admin",phone="0770000004",name="Admin",role="admin")
        response=self.client_for(admin).post('/api/users/',data)
        self.assertEqual(response.status_code,201); self.assertNotIn("password",response.data)
        self.assertTrue(User.objects.get(username="new").check_password(data["password"]))

    def test_station_operator_cannot_access_other_station_parcels(self):
        operator=User.objects.create_user(username="station",phone="0770000005",name="Station",role="station_operator")
        self.assertEqual(self.client_for(operator).get(f'/api/parcels/{self.parcel.code}/').status_code,404)

    def test_matching_creates_usable_task_and_field_access(self):
        user=User.objects.create_user(username="rider",phone="0770000006",name="Rider",role="rider")
        rider=Rider.objects.create(user=user,home_station=self.origin,status="approved",available=True)
        self.parcel.pickup_address="Pickup address"; self.parcel.save(update_fields=("pickup_address",))
        client=self.client_for(self.ops)
        response=client.post(f'/api/matching/{self.parcel.pk}/assign/',{"rider":rider.pk})
        self.assertEqual(response.status_code,200)
        task=Task.objects.get(parcel=self.parcel)
        field=self.client_for(user)
        self.assertEqual(field.get(f'/api/parcels/{self.parcel.code}/').status_code,200)
        self.assertEqual(field.post(f'/api/tasks/{task.pk}/accept/').status_code,200)
        code=issue_handover_code(self.parcel,"picked_up",self.customer)["code"]
        rejected=field.post(f'/api/tasks/{task.pk}/complete/',{"otp":"999999" if code!="999999" else "111111","to_status":"picked_up"})
        self.assertEqual(rejected.status_code,400)
        self.assertTrue(self.parcel.events.filter(accepted=False).exists())
        self.assertEqual(field.post(f'/api/tasks/{task.pk}/complete/',{"otp":code,"to_status":"picked_up"}).status_code,200)
        code=issue_handover_code(self.parcel,"at_origin_station",user)["code"]
        transition(self.parcel,self.ops,"at_origin_station",code)
        task.refresh_from_db(); self.assertEqual(task.status,"completed")
        self.assertEqual(field.patch(f'/api/tasks/{task.pk}/',{"status":"offered"}).status_code,405)

    def test_last_mile_requires_proof(self):
        rider=Rider.objects.create(user=self.customer,home_station=self.destination,status="approved")
        self.parcel.status="out_for_delivery"; self.parcel.assigned_rider=rider; self.parcel.delivery_choice="home"; self.parcel.save()
        task=Task.objects.create(parcel=self.parcel,type="last_mile_delivery",assigned_to=self.customer,status="accepted")
        code=issue_handover_code(self.parcel,"delivered",recipient=True)["code"]
        response=self.client_for(self.customer).post(f'/api/tasks/{task.pk}/complete/',{"otp":code,"to_status":"delivered"})
        self.assertEqual(response.status_code,400); self.assertIn("photo",str(response.data))

    def test_onboarding_cannot_submit_another_user_or_approve_itself(self):
        response=self.client_for(self.customer).post('/api/carriers/',{"user":self.ops.pk,"vehicle_type":"van","licence_no":"L1","capacity_kg":100,"document":receipt()},format='multipart')
        self.assertEqual(response.status_code,400); self.assertFalse(Carrier.objects.exists())
        self.assertEqual(self.client_for(self.customer).post('/api/onboarding/1/approve/',{"type":"carrier"}).status_code,403)

    def test_verified_payment_cannot_be_overwritten(self):
        customer=self.client_for(self.customer)
        self.assertEqual(customer.post(f'/api/parcels/{self.parcel.code}/mark-paid/',{"method":"cash","receipt_photo":receipt()},format="multipart").status_code,200)
        payment=Payment.objects.get(parcel=self.parcel)
        self.assertEqual(self.client_for(self.ops).post(f'/api/payments/{payment.pk}/verify/',{"status":"verified"}).status_code,200)
        self.assertEqual(customer.post(f'/api/parcels/{self.parcel.code}/mark-paid/',{"method":"cash"}).status_code,400)
        self.assertEqual(customer.patch(f'/api/payments/{payment.pk}/',{"amount":"0.01"}).status_code,405)

    def test_payout_requires_delivery_payment_and_balances_once(self):
        client=self.client_for(self.ops)
        data={"parcel":self.parcel.pk,"period":"2026-10","rider":"0","carrier":"0","station":"1"}
        self.assertEqual(client.post('/api/payouts/run/',data).status_code,400)
        self.parcel.status="delivered"; self.parcel.save(update_fields=("status",))
        Payment.objects.create(parcel=self.parcel,amount=self.parcel.price,status="verified")
        self.assertEqual(client.post('/api/payouts/run/',{**data,"carrier":"100"}).status_code,400)
        self.assertEqual(client.post('/api/payouts/run/',{**data,"carrier":"NaN"}).status_code,400)
        self.assertEqual(client.post('/api/payouts/run/',data).status_code,201)
        self.assertEqual(sum(Payout.objects.values_list("amount",flat=True)),self.parcel.price)
        self.assertEqual(client.post('/api/payouts/run/',data).status_code,400)

    def test_addresses_are_private_and_default_is_unique(self):
        client=self.client_for(self.customer)
        a=Address.objects.create(user=self.customer,label="A",city=self.origin.city,address="A",is_default=True)
        b=Address.objects.create(user=self.customer,label="B",city=self.origin.city,address="B")
        self.assertEqual(client.post(f'/api/addresses/{b.pk}/set-default/').status_code,200)
        self.assertEqual(Address.objects.filter(user=self.customer,is_default=True).count(),1)
        self.assertEqual(self.client_for(self.ops).get(f'/api/addresses/{a.pk}/').status_code,404)

    def test_delivery_address_validation_and_ticket_reply_author(self):
        client=self.client_for(self.customer)
        self.assertEqual(client.post(f'/api/parcels/{self.parcel.code}/delivery-choice/',{"choice":"home"}).status_code,400)
        self.assertEqual(client.post(f'/api/parcels/{self.parcel.code}/delivery-choice/',{"choice":"home","address":"Harare demo"}).status_code,200)
        response=client.post('/api/support/',{"subject":"Help","parcel_code":self.parcel.code})
        self.assertEqual(response.status_code,201)
        response=client.post(f'/api/support/{response.data["id"]}/reply/',{"body":"My reply","user_id":self.ops.pk})
        self.assertEqual(response.status_code,200); self.assertEqual(response.data["messages"][-1]["user_id"],self.customer.pk)

    def test_public_tracking_hides_internal_notes_and_actor(self):
        code=issue_handover_code(self.parcel,"at_origin_station",self.customer)["code"]
        transition(self.parcel,self.ops,"at_origin_station",code,"Internal confidential note")
        response=APIClient().get(f'/api/track/{self.parcel.recipient_access_token}/')
        self.assertNotIn("actor",str(response.data)); self.assertNotIn("Internal confidential",str(response.data))

@override_settings(DEBUG=True)
class DemoSeedTests(TestCase):
    def test_seed_is_idempotent_and_all_roles_can_login(self):
        call_command('seed_demo',stdout=StringIO())
        counts=(User.objects.count(),City.objects.count(),Station.objects.count(),RateTableEntry.objects.count(),Parcel.objects.count(),Task.objects.count(),Payout.objects.count())
        customer=User.objects.get(username="demo_customer"); customer.set_password("Changed123!"); customer.save()
        call_command('seed_demo',stdout=StringIO())
        self.assertEqual(counts,(User.objects.count(),City.objects.count(),Station.objects.count(),RateTableEntry.objects.count(),Parcel.objects.count(),Task.objects.count(),Payout.objects.count()))
        self.assertEqual(City.objects.values('province').distinct().count(),10)
        self.assertEqual(City.objects.count(),24)
        for role in User.Role.values:
            response=APIClient().post('/api/auth/token/',{"username":f"demo_{role}","password":"Changed123!" if role=="customer" else "Demo123!"})
            self.assertEqual(response.status_code,200,role); self.assertIn("access",response.data)
        self.assertTrue(User.objects.get(username="demo_admin").is_superuser)
        self.assertEqual(Rider.objects.get(user__username="demo_rider").status,"approved")
        self.assertEqual(Carrier.objects.get(user__username="demo_carrier").status,"approved")
