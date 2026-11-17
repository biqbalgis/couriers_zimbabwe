"""Create synthetic recording fixtures ONLY in the isolated acceptance database."""
import os
import sys
import json
from pathlib import Path
from io import BytesIO
from datetime import timedelta
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'mobile_test_settings'
import django
django.setup()
from django.conf import settings
assert Path(settings.DATABASES['default']['NAME']).resolve() == (Path(__file__).parent / 'artifacts' / 'acceptance.sqlite3').resolve()
from django.core.files.base import ContentFile
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from PIL import Image
from marketplace.models import User, Station, Rider, Carrier, Parcel, Task, Payment, Payout, StatusEvent
users = {role: User.objects.get(username='demo_' + role) for role in User.Role.values}
origin = Station.objects.get(name='Mutare Main')
destination = Station.objects.get(name='Chipinge Demo Parcel Point')
rider = Rider.objects.get(user__username='demo_rider_mutare')
carrier = Carrier.objects.get(user=users['carrier'])
image = BytesIO(); Image.new('RGB', (320,240), '#146c56').save(image, format='PNG')
application, created = User.objects.get_or_create(username='video_rider', defaults={'phone': '+263779880001', 'name': 'Video applicant', 'role': 'rider', 'verified': True})
if created: application.set_password('Demo123!'); application.save()
application_profile, _ = Rider.objects.get_or_create(user=application, defaults={'home_station':origin,'status':'pending','document':ContentFile(image.getvalue(),name='demo-identity.png')})
application_profile.status='pending'; application_profile.review_note=''; application_profile.save(update_fields=['status','review_note'])
output = {}
for uc, state, target, worker, leg in [
 ('UC09','booked','at_origin_station',None,None),
 ('UC10','booked','picked_up',rider.user,'first_mile_pickup'),
 ('UC11','booked','at_origin_station',None,None),
 ('UC12','booked','picked_up',rider.user,'first_mile_pickup'),
 ('UC13','picked_up','at_origin_station',None,None),
 ('UC14','at_origin_station','in_transit',carrier.user,'inter_town_transport'),
 ('UC15','at_destination_station','delivered',None,None),
 ('UC16','at_destination_station','delivered',None,None),
 ('UC17','out_for_delivery','delivered',rider.user,'last_mile_delivery'),
 ('UC18','booked','at_origin_station',None,None),
 ('UC19','picked_up','at_origin_station',None,None),
 ('UC20','delivered',None,rider.user,'first_mile_pickup'),
]:
 parcel = Parcel.objects.create(code=f'{800000 + Parcel.objects.count():06d}',sender=users['customer'],booked_by=users['customer'],sender_name='Demo sender',sender_phone=users['customer'].phone,recipient_name='Video recipient',recipient_phone='+263779880002',origin_station=origin,destination_station=destination,weight_band='0-2kg',price=12,status=state,notes=f'SYNTHETIC VIDEO FIXTURE {uc}',photo=ContentFile(image.getvalue(),name='demo-parcel.png'),assigned_rider=rider,assigned_carrier=carrier,current_holder=(rider.user if state=='picked_up' or state=='out_for_delivery' else origin.operator),pickup_address=('First Street, Mutare' if target=='picked_up' else ''),delivery_choice=('home' if uc=='UC17' else 'station'),delivery_address=('Video delivery address, Chipinge' if uc=='UC17' else ''))
 if target:
  parcel.handover_otp=make_password('123456');parcel.otp_target=target;parcel.otp_expires_at=timezone.now()+timedelta(hours=2);parcel.save()
 StatusEvent.objects.create(parcel=parcel,from_status='',to_status=state,actor=users['admin'],note='Synthetic scenario starting point, not real custody history')
 task = Task.objects.create(parcel=parcel,assigned_to=worker,type=leg,status=('offered' if uc=='UC10' else 'completed' if uc=='UC20' else 'accepted')) if worker else None
 if uc in ('UC11','UC14','UC16','UC17','UC20'):
  Payment.objects.create(parcel=parcel,amount=12,status=('pending' if uc=='UC11' else 'verified'),receipt_photo=ContentFile(image.getvalue(),name='demo-receipt.png'))
 if uc=='UC09':
  parcel.pickup_address='First Street, Mutare'; parcel.save(update_fields=['pickup_address'])
 if state=='booked':
  parcel.current_holder=users['customer']; parcel.save(update_fields=['current_holder'])
 elif state=='at_destination_station':
  parcel.current_holder=destination.operator; parcel.save(update_fields=['current_holder'])
 output[uc]={'code':parcel.code,'id':parcel.pk,'token':parcel.recipient_access_token,'task':task.pk if task else None}
print(json.dumps(output))
