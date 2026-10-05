const {test}=require('node:test');
const assert=require('node:assert/strict');
const overlay=require('../static/js/face-overlay.js');

test('video contain geometry includes top/bottom letterbox',()=>{
 const r=overlay.containRect(880,550,1280,720);
 assert.equal(r.width,880);assert.equal(r.height,495);assert.equal(r.top,27.5);assert.equal(r.left,0);
 assert.deepEqual(overlay.faceRect([640,360,800,540],r),{left:440,top:275,right:550,bottom:398.75});
});
test('portrait photo contain geometry includes left/right letterbox',()=>{
 const r=overlay.containRect(800,500,600,900);
 assert.ok(r.left>200);assert.equal(r.top,0);assert.equal(r.height,500);
});
test('invalid media and invalid/empty/offscreen face rectangles are ignored',()=>{
 assert.equal(overlay.containRect(0,200,1280,720),null);
 const r=overlay.containRect(320,240,1280,720);
 for(const bbox of [null,[1,2,3],[1,2,NaN,5],[40,40,30,50],[-30,20,-10,50]])assert.equal(overlay.faceRect(bbox,r),null);
 assert.deepEqual(overlay.faceRect([-10,-10,100,100],r),{left:0,top:30,right:25,bottom:55});
});
test('normal face label sits just above its frame',()=>{
 const r=overlay.containRect(880,550,1280,720),f=overlay.faceRect([640,360,800,540],r);
 assert.deepEqual(overlay.labelPosition(f,r,240,58,550,34),{left:440,top:209});
});
test('top edge label goes below face rather than being cropped',()=>{
 const r=overlay.containRect(320,240,1280,720),f=overlay.faceRect([0,0,180,160],r);
 assert.deepEqual(overlay.labelPosition(f,r,220,58,240,30),{left:8,top:78});
});
test('all four corners remain within video and above camera footer on mobile',()=>{
 const r=overlay.containRect(300,225,1280,720);
 for(const bbox of [[0,0,160,180],[1120,0,1280,180],[0,540,160,720],[1120,540,1280,720]]){
  const p=overlay.labelPosition(overlay.faceRect(bbox,r),r,260,58,225,30);
  assert.ok(p.left>=8&&p.left+260<=292);
  assert.ok(p.top>=r.top+8&&p.top+58<=195-8);
 }
});
test('recorded name, student id, real similarity and attendance status',()=>{
 assert.deepEqual(overlay.caption({name:'Thang',student_id:'SV001',confidence:86.52,recorded:true}),
  {name:'Thang',score:'Khớp 86.5%',detail:'SV001 · Đã điểm danh',tone:'recorded'});
});
test('unknown is never labeled attended even with high similarity',()=>{
 const c=overlay.caption({name:'Ghost',student_id:null,confidence:80,recorded:false});
 assert.equal(c.name,'Chưa xác định');assert.equal(c.detail,'Chưa đăng ký');assert.equal(c.tone,'warning');
});
test('recognized but rejected by session displays real reason',()=>{
 const c=overlay.caption({name:'Thang',student_id:'SV001',confidence:87,recorded:false,reason:'Không thuộc lớp'});
 assert.equal(c.detail,'SV001 · Không thuộc lớp');assert.equal(c.tone,'warning');
});
test('zero percent is not replaced with placeholder, invalid score never faked',()=>{
 assert.equal(overlay.caption({confidence:0}).score,'Khớp 0.0%');
 assert.equal(overlay.caption({confidence:NaN}).score,'Khớp —');
 assert.equal(overlay.caption({confidence:undefined}).score,'Khớp —');
});
