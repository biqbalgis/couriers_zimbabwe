import React,{useState} from 'react';
import {View} from 'react-native';
import {Button,Text} from 'react-native-paper';
import MapView,{Marker} from 'react-native-maps';
import AddressSearch from './AddressSearch';
import * as Location from 'expo-location';
import type {Values} from '../domain';
export default function LocationPin({prefix,values,onChange}:{prefix:'pickup'|'delivery';values:Values;onChange:(v:Values)=>void}){
 const [error,setError]=useState('');
 const lat=Number(values[prefix+'_latitude']),lon=Number(values[prefix+'_longitude']);
 const valid=!!values[prefix+'_latitude']&&!!values[prefix+'_longitude']&&Number.isFinite(lat)&&Number.isFinite(lon);
 const set=(latitude:number,longitude:number)=>onChange({...values,[prefix+'_latitude']:latitude.toFixed(6),[prefix+'_longitude']:longitude.toFixed(6)});
 return <View><AddressSearch prefix={prefix} values={values} onChange={onChange}/><Text>{prefix==='pickup'?'Pickup':'Delivery'} pin · tap map (EPSG:4326)</Text><MapView style={{height:240}} region={{latitude:valid?lat:-17.83,longitude:valid?lon:31.05,latitudeDelta:0.04,longitudeDelta:0.04}} onPress={e=>set(e.nativeEvent.coordinate.latitude,e.nativeEvent.coordinate.longitude)}>{valid&&<Marker coordinate={{latitude:lat,longitude:lon}}/>}</MapView><Button onPress={async()=>{try{const permission=await Location.requestForegroundPermissionsAsync();if(permission.status!=='granted')throw Error('Location permission denied. Choose a map pin or enter coordinates.');const position=await Location.getCurrentPositionAsync({accuracy:Location.Accuracy.Balanced});set(position.coords.latitude,position.coords.longitude)}catch(e){setError(String(e))}}}>Use my GPS location</Button><Button onPress={()=>onChange({...values,[prefix+'_latitude']:undefined,[prefix+'_longitude']:undefined})}>Clear pin</Button>{!!error&&<Text accessibilityRole="alert">{error}</Text>}</View>;
}
