import {useEffect,useRef,useState} from 'react';
import {Box,Button,Typography} from '@mui/material';
import Map from 'ol/Map';import View from 'ol/View';import TileLayer from 'ol/layer/Tile';import VectorLayer from 'ol/layer/Vector';import VectorSource from 'ol/source/Vector';import OSM from 'ol/source/OSM';import Feature from 'ol/Feature';import Point from 'ol/geom/Point';import {fromLonLat,toLonLat} from 'ol/proj';
import 'ol/ol.css';
import {AddressSearch} from './AddressSearch';
import type {FormValues} from './domain';
export function LocationPin({prefix,values,setValues}:{prefix:'pickup'|'delivery';values:FormValues;setValues:(v:FormValues)=>void}){
 const target=useRef<HTMLDivElement>(null),mapRef=useRef<Map>(),source=useRef(new VectorSource()),handler=useRef(setValues),current=useRef(values),[error,setError]=useState('');
 useEffect(()=>{handler.current=setValues;current.current=values},[setValues,values]);
 useEffect(()=>{if(!target.current)return;const map=new Map({target:target.current,layers:[new TileLayer({source:new OSM()}),new VectorLayer({source:source.current})],view:new View({center:fromLonLat([31.05,-17.83]),zoom:12})});mapRef.current=map;
 const click=map.on('singleclick',e=>{const [longitude,latitude]=toLonLat(e.coordinate);handler.current({...current.current,[prefix+'_latitude']:latitude.toFixed(6),[prefix+'_longitude']:longitude.toFixed(6)});});
 return()=>{map.un('singleclick',click.listener);map.setTarget(undefined);map.dispose();mapRef.current=undefined};
 },[prefix]);
 useEffect(()=>{const lat=Number(values[prefix+'_latitude']),lon=Number(values[prefix+'_longitude']);source.current.clear();if(values[prefix+'_latitude']&&values[prefix+'_longitude']&&Number.isFinite(lat)&&Number.isFinite(lon)){const coordinate=fromLonLat([lon,lat]);source.current.addFeature(new Feature(new Point(coordinate)));mapRef.current?.getView().setCenter(coordinate)}},[prefix,values]);
 return <Box><AddressSearch prefix={prefix} values={values} setValues={setValues}/><Typography>{prefix==='pickup'?'Pickup':'Delivery'} pin · tap map (EPSG:4326 coordinates)</Typography><Box ref={target} aria-label={prefix+' location map'} sx={{height:240,borderRadius:2,overflow:'hidden',border:1,borderColor:'divider'}}/><Button onClick={()=>{if(!navigator.geolocation){setError('GPS unavailable');return}navigator.geolocation.getCurrentPosition(p=>setValues({...values,[prefix+'_latitude']:p.coords.latitude.toFixed(6),[prefix+'_longitude']:p.coords.longitude.toFixed(6)}),e=>setError(e.message),{timeout:15000})}}>Use my GPS location</Button><Button onClick={()=>setValues({...values,[prefix+'_latitude']:undefined,[prefix+'_longitude']:undefined})}>Clear pin</Button>{error&&<Typography color="error">{error}</Typography>}</Box>;
}
