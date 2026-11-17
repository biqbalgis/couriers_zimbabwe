import {lazy,Suspense} from 'react';
import {Route,Routes} from 'react-router-dom';
import {Loading} from './workspace/Controls';
const Workspace=lazy(()=>import('./workspace/Workspace').then(m=>({default:m.Workspace})));
const Recipient=lazy(()=>import('./workspace/Workspace').then(m=>({default:m.RecipientScreen})));
const Landing=lazy(()=>import('./workspace/Workspace').then(m=>({default:m.RoleLanding})));
const Login=lazy(()=>import('./pages/Auth').then(m=>({default:m.Login})));
export default function App(){return <Suspense fallback={<Loading/>}><Routes><Route path="/" element={<Landing/>}/><Route path="/roles" element={<Landing/>}/><Route path="/login" element={<Login/>}/><Route path="/field/login" element={<Login field/>}/><Route path="/ops/login" element={<Login ops/>}/><Route path="/track/:token" element={<Recipient/>}/>{['app','field','carrier','station','ops','finance','support','admin'].map(area=><Route key={area} path={`/${area}/*`} element={<Workspace/>}/>)}<Route path="*" element={<Landing/>}/></Routes></Suspense>}
