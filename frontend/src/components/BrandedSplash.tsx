import {Box,LinearProgress,Stack,Typography} from '@mui/material';
import {LocalShipping} from '@mui/icons-material';
import {useEffect,useState} from 'react';

export function BrandedSplash(){
  const [visible,setVisible]=useState(()=>sessionStorage.getItem('splash-seen')!=='1');
  useEffect(()=>{if(!visible)return;const timer=setTimeout(()=>{sessionStorage.setItem('splash-seen','1');setVisible(false)},1200);return()=>clearTimeout(timer)},[visible]);
  if(!visible)return null;
  return <Box role="status" aria-label="Loading Pano Logistics" sx={{position:'fixed',inset:0,zIndex:10000,bgcolor:'primary.main',color:'white',display:'grid',placeItems:'center',p:3}}><Stack alignItems="center" gap={2} textAlign="center"><Box sx={{width:96,height:96,borderRadius:4,bgcolor:'secondary.main',color:'secondary.contrastText',display:'grid',placeItems:'center'}}><LocalShipping sx={{fontSize:56}}/></Box><Typography variant="h3" fontWeight={900}>Pano Logistics</Typography><Typography>Partner stations. Local people. Nationwide delivery.</Typography><LinearProgress color="secondary" sx={{width:'min(240px, 70vw)',borderRadius:2}}/></Stack></Box>
}
