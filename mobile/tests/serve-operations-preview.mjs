import {createServer} from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('./artifacts/operations-all/',import.meta.url));
const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.png':'image/png','.ico':'image/x-icon','.json':'application/json'};
createServer(async(req,res)=>{try{
 const relative=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\/+/,'');
 let path=resolve(root,relative||'index.html');
 if(!path.startsWith(resolve(root)+sep)){res.writeHead(403);res.end();return;}
 try{if(!(await stat(path)).isFile())path=resolve(root,'index.html')}catch{path=resolve(root,'index.html')}
 const data=await readFile(path);res.writeHead(200,{'Content-Type':types[extname(path)]||'application/octet-stream','Cache-Control':'no-store'});res.end(data);
 }catch{res.writeHead(500);res.end('Preview unavailable')}
}).listen(8083,'127.0.0.1',()=>console.log('Mobile operations preview: http://localhost:8083'));
