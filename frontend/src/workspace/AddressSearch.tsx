import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Button,Stack,Typography} from '@mui/material';
import {AppAPI} from '../AppAPI';
import {Failure} from './Controls';
import type {FormValues,LocationResult} from './domain';
export function AddressSearch({prefix,values,setValues}:{prefix:'pickup'|'delivery';values:FormValues;setValues:(v:FormValues)=>void}){
 const config=useQuery<{available:boolean}>({queryKey:['location-provider'],queryFn:()=>AppAPI.read('/locations/config/')});
 const [results,setResults]=useState<LocationResult[]>([]),[error,setError]=useState<unknown>(),[busy,setBusy]=useState(false);
 if(!config.data?.available)return <Typography variant="body2">Address search requires a configured provider. Set a map pin, use GPS, or enter coordinates.</Typography>;
 return <Stack gap={1}><Button disabled={busy||!values[prefix+'_address']} onClick={async()=>{setBusy(true);setError(undefined);try{setResults(await AppAPI.searchLocations(String(values[prefix+'_address'])))}catch(e){setError(e)}finally{setBusy(false)}}}>{busy?'Searching…':'Find '+prefix+' address'}</Button><Typography variant="caption">Suggestions are not a guarantee of deliverability. Confirm the address and pin with the recipient.</Typography>{error!=null&&<Failure error={error}/>} {results.map((r,i)=><Button key={i} onClick={()=>{setValues({...values,[prefix+'_address']:r.display_name,[prefix+'_latitude']:r.latitude,[prefix+'_longitude']:r.longitude});setResults([])}}>{r.display_name}</Button>)}</Stack>;
}
