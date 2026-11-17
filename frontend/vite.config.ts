import {defineConfig} from 'vite';import react from '@vitejs/plugin-react';import {VitePWA} from 'vite-plugin-pwa';
export default defineConfig({
  plugins:[react(),VitePWA({registerType:'autoUpdate',includeAssets:[],manifest:{name:'Pano Logistics',short_name:'Pano',theme_color:'#006400',background_color:'#fafafa',display:'standalone',start_url:'/'},workbox:{navigateFallback:'/index.html',runtimeCaching:[{urlPattern:/\/api\/(cities|stations|rates)\//,handler:'NetworkFirst',options:{cacheName:'public-catalog-cache',expiration:{maxEntries:100,maxAgeSeconds:86400}}}]}})],
  server:{proxy:{'/api':'http://localhost:8000'}},
  build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom','react-router-dom'],mui:['@mui/material','@mui/icons-material','@emotion/react','@emotion/styled'],'mui-grid':['@mui/x-data-grid'],data:['@tanstack/react-query','axios','idb']}}}}
});
