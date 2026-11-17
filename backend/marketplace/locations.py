"""Authenticated address search through an operator-configured Nominatim-compatible gateway."""
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from drf_spectacular.utils import extend_schema

class LocationQuery(serializers.Serializer):
    address=serializers.CharField(min_length=3,max_length=300)

class LocationResult(serializers.Serializer):
    display_name=serializers.CharField()
    latitude=serializers.CharField()
    longitude=serializers.CharField()

class ProviderUnavailable(APIException):
    status_code=503
    default_detail='Address search is unavailable. Use a map pin or enter GPS coordinates.'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def search_locations(address):
    endpoint=settings.GEOCODING_URL
    parsed=urlsplit(endpoint)
    if not endpoint or not parsed.hostname or parsed.scheme!='https' or parsed.query or parsed.fragment:raise ProviderUnavailable()
    headers={'User-Agent':settings.GEOCODING_USER_AGENT,'Accept':'application/json'}
    if settings.GEOCODING_TOKEN:headers['Authorization']='Bearer '+settings.GEOCODING_TOKEN
    url=endpoint+'?'+urlencode({'q':address,'format':'jsonv2','countrycodes':'zw','limit':5,'addressdetails':1})
    try:
        with build_opener(NoRedirect).open(Request(url,headers=headers),timeout=8) as response:
            if response.geturl().split('?',1)[0]!=endpoint:raise ProviderUnavailable()
            body=response.read(1_000_001)
            if len(body)>1_000_000:raise ProviderUnavailable()
            records=json.loads(body)
        if not isinstance(records,list):raise ProviderUnavailable()
        results=[]
        for item in records[:5]:
            lat=Decimal(str(item['lat']));lon=Decimal(str(item['lon']))
            if lat.is_finite() and lon.is_finite() and -90<=lat<=90 and -180<=lon<=180 and item.get('address',{}).get('country_code','zw')=='zw':
                results.append({'display_name':str(item['display_name'])[:1000],'latitude':format(lat,'.6f'),'longitude':format(lon,'.6f')})
        return results
    except (ValueError,KeyError,TypeError,InvalidOperation,OSError):raise ProviderUnavailable()

@extend_schema(parameters=[LocationQuery],responses=LocationResult(many=True))
@api_view(('GET',))
def location_search(request):
    query=LocationQuery(data=request.query_params);query.is_valid(raise_exception=True)
    return Response(search_locations(query.validated_data['address']))

@extend_schema(responses=dict)
@api_view(('GET',))
@permission_classes((AllowAny,))
def location_config(request):
    return Response({'available':bool(settings.GEOCODING_URL),'projection':'EPSG:4326'})
