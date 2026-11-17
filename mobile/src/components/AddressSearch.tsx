import React,{useState} from 'react';
import {View} from 'react-native';
import {Text,Button} from 'react-native-paper';
import {searchLocations} from '../api';
import {useLoad,ErrorBox} from './UI';
import type {Values,LocationResult} from '../domain';
export default function AddressSearch({prefix,values,onChange}:{prefix:'pickup'|'delivery';values:Values;onChange:(v:Values)=>void}){
 const config=useLoad<{available:boolean}>('/locations/config/',true);
 const [results,setResults]=useState<LocationResult[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 if(!config.data?.available)return <Text>Address search requires a configured provider. Set a map pin, use GPS, or enter coordinates.</Text>;
 return <View><Button loading={busy} disabled={busy||!values[prefix+'_address']} onPress={async()=>{setBusy(true);setError('');try{setResults(await searchLocations(String(values[prefix+'_address'])))}catch(e){setError(String(e))}finally{setBusy(false)}}}>Find {prefix} address</Button><Text>Suggestions are not a guarantee of deliverability. Confirm the address and pin with the recipient.</Text><ErrorBox error={error}/>{results.map((r,i)=><Button key={i} onPress={()=>{onChange({...values,[prefix+'_address']:r.display_name,[prefix+'_latitude']:r.latitude,[prefix+'_longitude']:r.longitude});setResults([])}}>{r.display_name}</Button>)}</View>;
}
