from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from . import tests as baseline
from .models import *
from .operations import *
from .services import create_parcel,record_payment,verify_payment,assign_parcel,transition
from .workflows import flag_exception

@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'}})
class OperationsTests(TestCase):
    def setUp(self):
        baseline.MarketplaceFlowTests.setUp(self)
        self.admin=User.objects.create_user(username='admin-ops',name='Admin',phone='+263771234560',role='admin')
        self.finance=User.objects.create_user(username='finance-ops',name='Finance',phone='+263771234561',role='finance')
        self.other=User.objects.create_user(username='other-ops',name='Other',phone='+263771234562',role='customer')
        self.dest_operator=User.objects.create_user(username='dest-ops',name='Destination',phone='+263771234563',role='station_operator')
        self.destination.operator=self.dest_operator;self.destination.save()
        self.rider_user=User.objects.create_user(username='rider-ops',name='Rider',phone='+263771234564',role='rider')
        self.rider=Rider.objects.create(user=self.rider_user,home_station=self.destination,status='approved',document=baseline.receipt(),available=True)
        self.carrier_user=User.objects.create_user(username='carrier-ops',name='Carrier',phone='+263771234565',role='carrier')
        self.carrier=Carrier.objects.create(user=self.carrier_user,status='approved',document=baseline.receipt(),capacity_kg=100,capacity_m3=1)
    def client_for(self,user):
        client=APIClient();client.force_authenticate(user);return client
    def paid(self):
        return Payment.objects.create(parcel=self.parcel,amount=self.parcel.price,status='verified')
    def request(self,kind,amount='0'):
        return open_case(self.parcel,self.customer,{'kind':kind,'amount':Decimal(amount),'reason':'Test issue'})
    def decide(self,case,action='approve',actor=None,**data):
        return decide_case(case,actor or self.ops,{'action':action,'note':'Reviewed test issue',**data})
    def trip(self,reverse=False,**values):
        return CarrierTrip.objects.create(carrier=self.carrier,origin_city=self.destination.city if reverse else self.origin.city,destination_city=self.origin.city if reverse else self.destination.city,departure_at=timezone.now()+timedelta(days=1),capacity_kg=20,**values)

    def test_unassigned_paid_cancellation_preserves_payment_and_requests_refund(self):
        payment=self.paid();case=self.request('cancellation')
        self.parcel.refresh_from_db();case.refresh_from_db()
        self.assertEqual(self.parcel.status,'cancelled');self.assertEqual(case.status,'resolved')
        self.assertEqual(self.parcel.operational_cases.get(kind='refund').amount,payment.amount)
        payment.refresh_from_db();self.assertEqual(payment.status,'verified')

    def test_assigned_cancellation_requires_decision_and_releases_capacity(self):
        trip=self.trip();assign_parcel(self.parcel,{'trip':trip})
        case=self.request('cancellation');self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.status,'booked');self.assertEqual(case.status,'requested')
        self.decide(case);self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.status,'cancelled');self.assertIsNone(self.parcel.trip_id)
        self.assertFalse(self.parcel.tasks.filter(status__in=('offered','accepted')).exists())

    def test_cancellation_at_origin_needs_sender_confirmed_physical_return(self):
        self.parcel.status='at_origin_station';self.parcel.current_holder=self.ops;self.parcel.save()
        self.decide(self.request('cancellation'));self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.status,'exception')
        case=self.parcel.operational_cases.get(kind='return')
        self.assertEqual(case.return_stage,'at_origin')
        code=return_action(case,self.customer,{'action':'code','note':'Receiving back'})['code']
        with self.assertRaises(ValidationError):transition(self.parcel,self.ops,'returned',code)
        result=return_action(case,self.ops,{'action':'confirm','note':'Sender collected','otp':code,'photo':baseline.receipt()})
        self.assertEqual(result['stage'],'returned')
        self.parcel.refresh_from_db();self.assertEqual(self.parcel.current_holder_id,self.customer.pk)

    def test_refund_permissions_amount_limit_reference_and_no_silent_transfer(self):
        self.paid();case=self.request('refund','10')
        with self.assertRaises(PermissionDenied):self.decide(case,actor=self.customer,amount=Decimal('10'))
        with self.assertRaises(ValidationError):self.decide(case,actor=self.finance,amount=Decimal('11'))
        self.decide(case,actor=self.finance,amount=Decimal('10'))
        with self.assertRaises(ValidationError):self.decide(case,'pay',self.finance)
        self.decide(case,'pay',self.finance,reference='BANK-REFUND-1')
        case.refresh_from_db();self.assertEqual(case.status,'paid')
        self.assertEqual(AdminAudit.objects.filter(action='case_pay').count(),1)
        second=self.request('refund','1')
        with self.assertRaises(ValidationError):self.decide(second,actor=self.finance,amount=Decimal('1'))

    def test_claim_evidence_and_combined_liability_limit(self):
        self.parcel.declared_value=Decimal('200');self.parcel.policy_snapshot={**DEFAULT_POLICY,'liability_limit':'50.00','reviewed':True};self.parcel.save()
        case=self.request('damage','40')
        with self.assertRaises(ValidationError):self.decide(case,actor=self.finance,amount=Decimal('40'))
        CustodyEvidence.objects.create(parcel=self.parcel,case=case,uploaded_by=self.customer,photo=baseline.receipt(),condition='damaged')
        with self.assertRaises(ValidationError):self.decide(case,actor=self.finance,amount=Decimal('51'))
        self.decide(case,actor=self.finance,amount=Decimal('40'))
        other=self.request('loss','11');CustodyEvidence.objects.create(parcel=self.parcel,case=other,uploaded_by=self.customer,photo=baseline.receipt(),condition='missing')
        with self.assertRaises(ValidationError):self.decide(other,actor=self.finance,amount=Decimal('11'))

    def test_failed_delivery_requires_accepted_rider_and_escalates_at_limit(self):
        self.parcel.status='out_for_delivery';self.parcel.current_holder=self.rider_user;self.parcel.save()
        with self.assertRaises(PermissionDenied):record_attempt(self.parcel,self.rider_user,{'outcome':'unavailable','next_action':'contact','note':'No answer'})
        Task.objects.create(parcel=self.parcel,assigned_to=self.rider_user,type='last_mile_delivery',status='accepted')
        for _ in range(3):record_attempt(self.parcel,self.rider_user,{'outcome':'unreachable','next_action':'contact','note':'No answer'})
        self.parcel.refresh_from_db();self.assertEqual(self.parcel.status,'exception')
        self.assertEqual(self.parcel.delivery_attempts.count(),3)
        self.assertEqual(self.parcel.operational_cases.filter(kind='return',status='requested').count(),1)

    def test_return_trip_receiver_codes_photos_and_final_sender_confirmation(self):
        self.parcel.status='at_destination_station';self.parcel.current_holder=self.dest_operator;self.parcel.save()
        case=self.decide(self.request('return'))
        trip=self.trip(reverse=True)
        return_action(case,self.ops,{'action':'assign','trip':trip,'note':'Reverse manifest'})
        for actor,confirmer in [(self.carrier_user,self.dest_operator),(self.ops,self.carrier_user),(self.ops,self.customer)]:
            code=return_action(case,confirmer,{'action':'code','note':'Independent approval'})['code']
            with self.assertRaises(PermissionDenied):return_action(case,self.other,{'action':'confirm','otp':code,'note':'No'})
            invalid=return_action(case,actor,{'action':'confirm','otp':'999999' if code!='999999' else '000000','note':'Wrong'})
            self.assertTrue(invalid['invalid'])
            with self.assertRaises(ValidationError):return_action(case,actor,{'action':'confirm','otp':code,'note':'No photo'})
            return_action(case,actor,{'action':'confirm','otp':code,'photo':baseline.receipt(),'note':'Condition checked'})
        self.parcel.refresh_from_db();case.refresh_from_db()
        self.assertEqual(self.parcel.status,'returned');self.assertEqual(case.status,'resolved')
        self.assertEqual(case.evidence.count(),3)

    def test_reused_receipt_blocks_verification_until_audited_review(self):
        record_payment(self.parcel,{'receipt_photo':baseline.receipt(),'transaction_reference':'REUSED'})
        second=create_parcel({'recipient_name':'Other','recipient_phone':'+263771000000','origin_station':self.origin,'destination_station':self.destination,'weight_band':'0-2kg'},self.customer)
        payment=record_payment(second,{'receipt_photo':baseline.receipt(),'transaction_reference':'REUSED'})
        self.assertEqual(set(payment.fraud_flags),{'receipt_reused','reference_reused'})
        with self.assertRaises(ValidationError):verify_payment(payment,self.finance,'verified')
        client=self.client_for(self.finance)
        self.assertEqual(client.post('/api/payments/'+str(payment.pk)+'/fraud-review/',{'note':'Verified independent original bank statement'}).status_code,200)
        verify_payment(payment,self.finance,'verified');self.assertTrue(AdminAudit.objects.filter(action='payment_fraud_review').exists())

    def test_weight_volume_and_return_reservations(self):
        self.parcel.length_cm=self.parcel.width_cm=self.parcel.height_cm=Decimal('100');self.parcel.save()
        trip=self.trip(capacity_m3=Decimal('0.5000'))
        with self.assertRaises(ValidationError):assign_parcel(self.parcel,{'trip':trip})
        trip.capacity_m3=Decimal('1.0000');trip.save();assign_parcel(self.parcel,{'trip':trip})
        second=create_parcel({'recipient_name':'Other','recipient_phone':'+263771000000','origin_station':self.origin,'destination_station':self.destination,'weight_band':'0-2kg','length_cm':Decimal('1'),'width_cm':Decimal('1'),'height_cm':Decimal('1')},self.customer)
        with self.assertRaises(ValidationError):assign_parcel(second,{'trip':trip})

    def test_booking_policy_restrictions_dimensions_and_gps(self):
        with self.assertRaises(ValidationError):validate_booking({'contents_category':'hazardous'})
        with self.assertRaises(ValidationError):validate_booking({'length_cm':Decimal('5')})
        with self.assertRaises(ValidationError):validate_booking({'pickup_latitude':Decimal('-17.83')})
        with self.assertRaises(ValidationError):validate_booking({'pickup_latitude':Decimal('100'),'pickup_longitude':Decimal('31')})
        PlatformSettings.objects.create(key='operations-policy',value={'dimensions_required':True,'max_length_cm':'5'})
        with self.assertRaises(ValidationError):validate_booking({})
        with self.assertRaises(ValidationError):validate_booking({'length_cm':Decimal('6'),'width_cm':Decimal('5'),'height_cm':Decimal('5')})

    def test_suspension_reverification_expired_documents_and_owner_cannot_override(self):
        partner_action(self.carrier,self.ops,{'action':'suspend','note':'Safety review'})
        self.carrier.refresh_from_db();self.assertFalse(eligible_partner(self.carrier))
        self.carrier.document_expires_at=timezone.localdate()-timedelta(days=1);self.carrier.save()
        with self.assertRaises(ValidationError):partner_action(self.carrier,self.ops,{'action':'reactivate','note':'Review'})
        client=self.client_for(self.carrier_user)
        response=client.patch('/api/carriers/'+str(self.carrier.pk)+'/',{'suspended':False,'status':'approved'})
        self.assertEqual(response.status_code,200);self.carrier.refresh_from_db();self.assertTrue(self.carrier.suspended)

    def test_private_cases_evidence_receipts_exports_audit_and_overrides(self):
        case=self.request('damage')
        photo=CustodyEvidence.objects.create(parcel=self.parcel,case=case,uploaded_by=self.customer,photo=baseline.receipt(),condition='damaged')
        other=self.client_for(self.other);owner=self.client_for(self.customer);ops=self.client_for(self.ops)
        self.assertEqual(other.get('/api/operational-cases/').data['count'],0)
        self.assertEqual(other.get('/api/files/'+photo.photo.name).status_code,403)
        self.assertEqual(owner.get('/api/files/'+photo.photo.name).status_code,200)
        self.assertEqual(other.get('/api/parcels/'+self.parcel.code+'/receipt/').status_code,404)
        self.assertEqual(owner.get('/api/parcels/'+self.parcel.code+'/receipt/').status_code,200)
        self.assertEqual(owner.get('/api/exports/customers/').status_code,403)
        self.assertEqual(ops.get('/api/exports/shipments/').status_code,200)
        self.assertEqual(owner.post('/api/parcels/'+self.parcel.code+'/override/',{'note':'No','recipient_name':'Changed'}).status_code,403)
        self.assertEqual(ops.post('/api/parcels/'+self.parcel.code+'/override/',{'note':'Verified spelling','recipient_name':'Changed'}).status_code,200)
        self.assertTrue(AdminAudit.objects.filter(action='parcel_override').exists())
        self.assertEqual(owner.patch('/api/operational-cases/'+str(case.pk)+'/',{'status':'paid'}).status_code,405)

    def test_admin_changes_audited_without_password_and_log_append_only(self):
        response=self.client_for(self.admin).patch('/api/users/'+str(self.other.pk)+'/',{'role':'support','password':'HiddenSecret123'})
        self.assertEqual(response.status_code,200)
        event=AdminAudit.objects.get(action='user_changed',target='user:'+str(self.other.pk))
        self.assertEqual(event.before['role'],'customer');self.assertEqual(event.after['role'],'support')
        self.assertNotIn('HiddenSecret',str(event.after))
        with self.assertRaises(ModelValidationError):AdminAudit.objects.filter(pk=event.pk).delete()
        event.reason='Tamper'
        with self.assertRaises(ModelValidationError):event.save()

    def test_policy_permissions_notification_config_and_honest_insurance(self):
        owner=self.client_for(self.customer);admin=self.client_for(self.admin)
        self.assertEqual(owner.put('/api/operations/policy/',DEFAULT_POLICY,format='json').status_code,403)
        self.assertEqual(admin.put('/api/operations/policy/',{**DEFAULT_POLICY,'insurance_available':True},format='json').status_code,400)
        self.assertEqual(admin.put('/api/operations/policy/',{**DEFAULT_POLICY,'notifications':[]},format='json').status_code,200)
        count=Notification.objects.count()
        from .services import queue_notifications
        queue_notifications(self.parcel,'failed_delivery');self.assertEqual(Notification.objects.count(),count)
        self.assertEqual(admin.post('/api/settings/',{'key':'operations-policy','value':{}},format='json').status_code,400)

    def test_delegated_refund_approval_and_payment_are_separate_audited_permissions(self):
        self.paid();case=self.request('refund','5')
        with self.assertRaises(PermissionDenied):self.decide(case,actor=self.ops,amount=Decimal('5'))
        admin=self.client_for(self.admin)
        response=admin.patch('/api/users/'+str(self.ops.pk)+'/',{'operational_permissions':['approve_refund']},format='json')
        self.assertEqual(response.status_code,200)
        actor=User.objects.get(pk=self.ops.pk)
        self.decide(case,actor=actor,amount=Decimal('5'))
        with self.assertRaises(PermissionDenied):self.decide(case,'pay',actor,reference='DELEGATED-PAY-1')
        response=admin.patch('/api/users/'+str(self.ops.pk)+'/',{'operational_permissions':['record_refund_payment']},format='json')
        self.assertEqual(response.status_code,200)
        self.decide(case,'pay',User.objects.get(pk=self.ops.pk),reference='DELEGATED-PAY-1')
        self.assertTrue(AdminAudit.objects.filter(action='user_permissions_changed').exists())
        self.assertEqual(admin.patch('/api/users/'+str(self.customer.pk)+'/',{'operational_permissions':['approve_refund']},format='json').status_code,400)

    def test_exception_correction_appends_event_and_inbox_is_private(self):
        flag_exception(self.parcel,self.ops,'Incorrect exception selected')
        client=self.client_for(self.ops)
        self.assertEqual(client.post('/api/parcels/'+self.parcel.code+'/override/',{'note':'Confirmed current holder; restore recorded state','restore_previous_status':True},format='json').status_code,200)
        self.parcel.refresh_from_db();self.assertEqual(self.parcel.status,'booked')
        self.assertTrue(self.parcel.events.filter(from_status='exception',to_status='booked',note__startswith='Audited').exists())
        other=self.client_for(self.other)
        self.assertEqual(other.get('/api/operations/inbox/').data['count'],0)

    def test_geocoding_is_configured_authenticated_and_rejects_bad_coordinates(self):
        from unittest.mock import patch,MagicMock
        from .locations import search_locations
        self.assertEqual(APIClient().get('/api/locations/search/',{'address':'Mutare'}).status_code,401)
        self.assertEqual(self.client_for(self.customer).get('/api/locations/search/',{'address':'Mutare'}).status_code,503)
        response=MagicMock()
        response.__enter__.return_value=response
        response.geturl.return_value='https://geocoder.example/search?q=Mutare'
        response.read.return_value=b'[{"lat":"-18.97","lon":"32.67","display_name":"Mutare","address":{"country_code":"zw"}},{"lat":"120","lon":"300","display_name":"Invalid"}]'
        with override_settings(GEOCODING_URL='https://geocoder.example/search'),patch('marketplace.locations.build_opener') as opener:
            opener.return_value.open.return_value=response
            result=search_locations('Mutare')
            self.assertEqual(result,[{'display_name':'Mutare','latitude':'-18.970000','longitude':'32.670000'}])

    def test_resolved_handover_failures_leave_inbox_and_trip_capacity_is_prefetched(self):
        from django.db.models import Prefetch
        from .serializers import TripSerializer
        StatusEvent.objects.create(parcel=self.parcel,from_status='booked',to_status='at_origin_station',actor=self.ops,accepted=False,note='Rejected handover')
        client=self.client_for(self.ops)
        self.assertEqual(client.get('/api/operations/inbox/').data['count'],1)
        StatusEvent.objects.create(parcel=self.parcel,from_status='booked',to_status='at_origin_station',actor=self.ops,accepted=True,note='Corrected handover')
        self.assertEqual(client.get('/api/operations/inbox/').data['count'],0)
        trip=self.trip(capacity_m3=Decimal('0.5'))
        serializer=TripSerializer(trip,data={'active':False},partial=True)
        self.assertTrue(serializer.is_valid(),serializer.errors)
        queryset=CarrierTrip.objects.select_related('carrier__user','origin_city','destination_city').prefetch_related('parcels',Prefetch('return_cases',queryset=OperationalCase.objects.filter(status__in=('approved','in_progress')).select_related('parcel'),to_attr='capacity_returns'))
        with self.assertNumQueries(3):
            result=TripSerializer(queryset,many=True).data
        self.assertEqual(Decimal(result[0]['remaining_m3']),Decimal('0.5'))

    def test_dispatch_rechecks_expired_documents_and_handover_photo_is_linked(self):
        from .workflows import issue_handover_code
        code=issue_handover_code(self.parcel,'at_origin_station',self.customer)['code']
        transition(self.parcel,self.ops,'at_origin_station',code,photo=baseline.receipt())
        evidence=self.parcel.custody_evidence.get()
        self.assertEqual(evidence.event.to_status,'at_origin_station')
        self.paid();trip=self.trip();assign_parcel(self.parcel,{'trip':trip})
        self.parcel.tasks.update(status='accepted')
        self.carrier.document_expires_at=timezone.localdate()-timedelta(days=1);self.carrier.save()
        code=issue_handover_code(self.parcel,'in_transit',self.ops)['code']
        with self.assertRaises(ValidationError):transition(self.parcel,self.carrier_user,'in_transit',code)
