import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(process.argv[2]);
const manifest=JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'));
assert.equal(manifest.length,26);
const files=[];
for(const item of manifest){
 assert.equal(item.status,'recorded',item.id);
 const file=path.join(root,item.file);
 const data=JSON.parse(execFileSync('ffprobe',['-v','error','-show_entries','stream=width,height,codec_name','-show_entries','format=duration','-of','json',file],{encoding:'utf8'}));
 assert.equal(data.streams[0].width,390);assert.equal(data.streams[0].height,844);assert(Number(data.format.duration)>=5);
 execFileSync('ffmpeg',['-hide_banner','-v','error','-i',file,'-f','null','-'],{stdio:['ignore','ignore','pipe']});
 files.push({id:item.id,...data.streams[0],seconds:Number(data.format.duration),decoded:true});
 console.log(item.id,'decoded');
}
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'index.html')).href);assert.equal(await page.locator('video').count(),26);
 for(const index of [0,25]){
  const video=page.locator('video').nth(index);await video.scrollIntoViewIfNeeded();await video.evaluate(v=>v.play());await page.waitForTimeout(1200);assert(await video.evaluate(v=>v.currentTime>0),'Video did not play');await video.evaluate(v=>v.pause());
 }
 assert.equal(errors.length,0);await page.screenshot({path:path.join(root,'gallery-check.png')});
 await writeFile(path.join(root,'validation.json'),JSON.stringify({files,galleryVideos:26,firstAndLastPlaybackPassed:true,errors},null,2));
}finally{await browser.close();}
console.log('PASS: 26 decoded videos and gallery playback');
