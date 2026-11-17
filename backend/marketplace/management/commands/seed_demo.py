from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from marketplace.models import Address,Carrier,City,Parcel,Payment,PlatformSettings,Rider,Station,SupportTicket,Task,User,RateTableEntry
from marketplace.services import create_parcel,run_payout,seed_transition as transition
from marketplace.models import CarrierTrip,PilotRoute,IntegrationDelivery,StatusEvent

# Approximate city-centre coordinates in EPSG:4326, not surveyed stations.
PLACES=[
    ("Harare","Harare",-17.8252,31.0335),("Bulawayo","Bulawayo",-20.1500,28.5833),
    ("Mutare","Manicaland",-18.9707,32.6709),("Gweru","Midlands",-19.4500,29.8167),
    ("Masvingo","Masvingo",-20.0637,30.8277),("Chinhoyi","Mashonaland West",-17.3667,30.2000),
    ("Bindura","Mashonaland Central",-17.3000,31.3333),("Marondera","Mashonaland East",-18.1833,31.5500),
    ("Gwanda","Matabeleland South",-20.9333,29.0000),("Lupane","Matabeleland North",-18.9333,27.7500),
    ("Victoria Falls","Matabeleland North",-17.9333,25.8333),("Hwange","Matabeleland North",-18.3667,26.5000),
    ("Kwekwe","Midlands",-18.9167,29.8167),("Kadoma","Mashonaland West",-18.3333,29.9167),
    ("Chegutu","Mashonaland West",-18.1300,30.1400),("Kariba","Mashonaland West",-16.5167,28.8000),
    ("Chiredzi","Masvingo",-21.0500,31.6667),("Beitbridge","Matabeleland South",-22.2167,30.0000),
    ("Rusape","Manicaland",-18.5333,32.1167),("Chipinge","Manicaland",-20.1883,32.6236),
    ("Zvishavane","Midlands",-20.3333,30.0333),("Shurugwi","Midlands",-19.6667,30.0000),
    ("Norton","Mashonaland West",-17.8833,30.7000),("Chitungwiza","Harare",-18.0000,31.1000),
]

class Command(BaseCommand):
    help="Create an idempotent demonstration network and users"
    def add_arguments(self,parser):
        parser.add_argument("--reset-passwords",action="store_true",help="Explicitly reset existing demo passwords.")
    @transaction.atomic
    def handle(self,*args,**kwargs):
        if not settings.DEBUG: raise CommandError("Demo seed requires DJANGO_DEBUG=1.")
        users={}
        for role in User.Role.values:
            username=f"demo_{role}"
            user,_=User.objects.get_or_create(username=username,defaults={"phone":f"+26377{len(users):07d}","name":role.replace('_',' ').title(),"role":role,"verified":True})
            if _ or kwargs["reset_passwords"]: user.set_password("Demo123!"); user.save(update_fields=("password",))
            if role=="admin" and user.role=="admin": user.is_staff=True; user.is_superuser=True; user.save(update_fields=("is_staff","is_superuser"))
            users[role]=user
        cities={name:City.objects.get_or_create(name=name,province=province)[0] for name,province,lat,lon in PLACES}
        specs=[("Avondale Partner Shop","Harare","Avondale, Harare","0772 100 001"),("CBD Parcel Point","Harare","Jason Moyo Ave, Harare","0772 100 002"),("Mbare Market Station","Harare","Mbare, Harare","0772 100 003"),("Bulawayo Central","Bulawayo","Fife Street, Bulawayo","0772 200 001"),("Mutare Main","Mutare","First Street, Mutare","0772 300 001"),("Gweru Hub Partner","Gweru","Main Street, Gweru","0772 400 001")]
        stations={}
        for name,city,address,pay in specs:
            stations[name]=Station.objects.get_or_create(name=name,city=cities[city],defaults={"address":address,"operator":users[User.Role.STATION_OPERATOR],"payment_number":pay})[0]
        for name,province,lat,lon in PLACES:
            station=next((s for s in stations.values() if s.city_id==cities[name].pk),None)
            if station is None:
                station,_=Station.objects.get_or_create(name=f"{name} Demo Parcel Point",city=cities[name],defaults={"address":f"Demo partner point, {name}, Zimbabwe","operator":users["station_operator"],"payment_number":users["station_operator"].phone})
            if station.latitude is None:
                station.latitude=lat; station.longitude=lon; station.save(update_fields=("latitude","longitude"))
            stations[name]=station
        for name,lat,lon in (("Avondale Partner Shop",-17.8000,31.0300),("Mbare Market Station",-17.8610,31.0350)):
            station=stations[name]
            if station.latitude is None: station.latitude=lat; station.longitude=lon; station.save(update_fields=("latitude","longitude"))
        for station in Station.objects.filter(latitude__isnull=True).select_related("city"):
            coords=next(((lat,lon) for name,province,lat,lon in PLACES if station.city.name==name and station.city.province==province),None)
            if coords:
                station.latitude,station.longitude=coords; station.save(update_fields=("latitude","longitude"))
        for origin in cities:
            for destination in cities:
                base=4 if origin==destination else 12
                if {origin,destination}=={"Harare","Mutare"}: base=8
                if {origin,destination}=={"Harare","Gweru"}: base=9
                for band,extra in (("0-2kg",0),("2-5kg",4),("5-10kg",8)):
                    RateTableEntry.objects.get_or_create(origin_city=cities[origin],destination_city=cities[destination],weight_band=band,station_override=None,defaults={"price":base+extra})
        RateTableEntry.objects.get_or_create(origin_city=cities['Harare'],destination_city=cities['Bulawayo'],weight_band='0-2kg',station_override=stations['Avondale Partner Shop'],defaults={"price":10})
        rider,_=Rider.objects.get_or_create(user=users["rider"],defaults={"home_station":stations["Harare"],"status":"approved","available":True})
        carrier,_=Carrier.objects.get_or_create(user=users["carrier"],defaults={"vehicle_type":"Demo delivery van","licence_no":"DEMO-ZW-001","capacity_kg":1000,"status":"approved"})
        Address.objects.get_or_create(user=users["customer"],label="Home",defaults={"contact_name":"Demo Customer","phone":users["customer"].phone,"city":cities["Harare"],"address":"Demo address, Avondale, Harare","is_default":not Address.objects.filter(user=users["customer"],is_default=True).exists()})
        PlatformSettings.objects.get_or_create(key="network",defaults={"value":{"currency":"USD","support_hours":"08:00-20:00","timezone":"Africa/Harare","notification_sender":"Pano Logistics"}})
        # Establish the selected pilot while retaining historical demo records.
        PilotRoute.objects.get_or_create(name="Mutare–Chipinge pilot",origin_city=cities["Mutare"],destination_city=cities["Chipinge"],defaults={"active":True})
        pilot_users={}
        for index,(username,role,city) in enumerate((("demo_rider_mutare","rider","Mutare"),("demo_rider_chipinge","rider","Chipinge"),("demo_station_chipinge","station_operator","Chipinge"),("demo_recipient","customer","Chipinge"))):
            user,created=User.objects.get_or_create(username=username,defaults={"phone":f"+2637800000{index:02d}","name":username.replace("demo_","").replace("_"," ").title(),"role":role,"verified":True})
            if created or kwargs["reset_passwords"]: user.set_password("Demo123!"); user.save(update_fields=("password",))
            pilot_users[username]=user
            if role=="rider": Rider.objects.get_or_create(user=user,defaults={"home_station":stations[city],"status":"approved","available":True})
        station=stations["Chipinge"]
        if station.operator_id==users["station_operator"].pk:
            station.operator=pilot_users["demo_station_chipinge"]; station.save(update_fields=("operator",))
        for origin,destination in (("Mutare","Chipinge"),("Chipinge","Mutare")):
            if not CarrierTrip.objects.filter(carrier=carrier,origin_city=cities[origin],destination_city=cities[destination],departure_at__gt=timezone.now(),active=True).exists():
                CarrierTrip.objects.create(carrier=carrier,origin_city=cities[origin],destination_city=cities[destination],departure_at=timezone.now()+timedelta(days=7),capacity_kg=1000)
        marker="Mutare–Chipinge pilot booking"
        if not Parcel.objects.filter(notes=marker,sender=users["customer"]).exists():
            create_parcel({"recipient_name":"Demo Recipient","recipient_phone":pilot_users["demo_recipient"].phone,"origin_station":stations["Mutare"],"destination_station":stations["Chipinge"],"weight_band":"0-2kg","notes":marker},users["customer"])
        # Backfill archive outbox for pre-existing events without changing their history.
        archived=set(IntegrationDelivery.objects.filter(kind="event_log").values_list("payload__event_id",flat=True))
        for event in StatusEvent.objects.exclude(pk__in=archived):
            IntegrationDelivery.objects.create(kind="event_log",payload={"event_id":event.pk,"parcel_id":event.parcel_id,"from_status":event.from_status,"to_status":event.to_status,"actor_id":event.actor_id,"released_by_id":event.released_by_id,"received_by_id":event.received_by_id if event.received_by_id else (None if event.recipient_confirmed else event.actor_id),"recipient_confirmed":event.recipient_confirmed,"accepted":event.accepted,"otp_used":event.otp_used,"note":event.note,"timestamp":event.timestamp.isoformat()})
        self.stdout.write(self.style.SUCCESS(f"Pilot ready: Mutare–Chipinge. {City.objects.count()} cities, {Station.objects.count()} stations, {User.objects.filter(username__startswith='demo_').count()} demo accounts. New demo passwords: Demo123!"))
