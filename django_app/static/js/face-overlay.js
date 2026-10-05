/* Geometry is in CSS pixels so face labels stay readable on small screens. */
(function(root,factory){
 "use strict";
 const policy=factory();
 if(typeof module==="object"&&module.exports)module.exports=policy;
 else root.VistaFaceOverlay=policy;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const clamp=(value,min,max)=>Math.min(Math.max(value,min),Math.max(min,max));
 function containRect(stageWidth,stageHeight,imageWidth,imageHeight){
  if(![stageWidth,stageHeight,imageWidth,imageHeight].every(n=>Number.isFinite(n)&&n>0))return null;
  const scale=Math.min(stageWidth/imageWidth,stageHeight/imageHeight);
  const width=imageWidth*scale,height=imageHeight*scale;
  return {left:(stageWidth-width)/2,top:(stageHeight-height)/2,width,height,scale,imageWidth,imageHeight};
 }
 function faceRect(bbox,media){
  if(!media||!Array.isArray(bbox)||bbox.length!==4||!bbox.every(Number.isFinite))return null;
  const [x1,y1,x2,y2]=bbox;
  if(x2<=x1||y2<=y1)return null;
  const left=clamp(x1,0,media.imageWidth),top=clamp(y1,0,media.imageHeight);
  const right=clamp(x2,0,media.imageWidth),bottom=clamp(y2,0,media.imageHeight);
  if(right<=left||bottom<=top)return null;
  return {left:media.left+left*media.scale,top:media.top+top*media.scale,
   right:media.left+right*media.scale,bottom:media.top+bottom*media.scale};
 }
 function labelPosition(face,media,labelWidth,labelHeight,stageHeight,footerHeight=0){
  const gap=8,minX=media.left+gap,minY=media.top+gap;
  const maxX=media.left+media.width-labelWidth-gap;
  const maxY=Math.min(media.top+media.height,stageHeight-footerHeight)-labelHeight-gap;
  let top=face.top-labelHeight-gap;
  if(top<minY)top=face.bottom+gap;
  if(top>maxY)top=face.top+gap;
  return {left:clamp(face.left,minX,maxX),top:clamp(top,minY,maxY)};
 }
 function caption(result){
  const identified=Boolean(result.student_id);
  const score=typeof result.confidence==="number"&&Number.isFinite(result.confidence)
   ?clamp(result.confidence,0,100).toFixed(1)+"%":"—";
  const status=result.recorded?"Đã điểm danh":result.reason||(identified?"Chưa ghi nhận":"Chưa đăng ký");
  return {name:identified?result.name||result.student_id:"Chưa xác định",score:"Khớp "+score,
   detail:(identified?result.student_id+" · ":"")+status,
   tone:result.recorded?"recorded":"warning"};
 }
 return {containRect,faceRect,labelPosition,caption};
});
