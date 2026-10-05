/* VISTA local workspace — all API writes include Django CSRF. */
(() => {
"use strict";
const $=(s,p=document)=>p.querySelector(s), $$=(s,p=document)=>[...p.querySelectorAll(s)];
const page=document.body.dataset.page;
let toastTimer;
function toast(text,type="success"){const n=$("#toast");n.textContent=text;n.className=type;n.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>n.hidden=true,5500);}
async function api(url,options={}){
 const response=await fetch(url,{...options,headers:{"Content-Type":"application/json","X-CSRFToken":$('meta[name="csrf-token"]').content,...options.headers},credentials:"same-origin"});
 let result;try{result=await response.json();}catch{throw new Error(response.status===403?"Phiên làm việc hết hạn. Vui lòng tải lại trang.":"Máy chủ trả về dữ liệu không hợp lệ.");}
 if(!response.ok||!result.success)throw new Error(result.error||"Không thể thực hiện thao tác.");return result;
}
function message(n,text,type=""){n.textContent=text;n.className="form-message "+type;}
function busy(n,on){if(on){n.dataset.label=n.textContent.trim();n.disabled=true;n.textContent="Đang xử lý…";}else{n.disabled=false;n.textContent=n.dataset.label;}}
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;}
function clock(){const now=new Date();$("#currentTime").textContent=now.toLocaleDateString("vi-VN",{weekday:"short",day:"2-digit",month:"2-digit",timeZone:"Asia/Ho_Chi_Minh"})+" · "+now.toLocaleTimeString("vi-VN",{hour:"2-digit",minute:"2-digit",timeZone:"Asia/Ho_Chi_Minh"});}
clock();setInterval(clock,30000);
const menu=$("#menuToggle");menu.addEventListener("click",()=>menu.setAttribute("aria-expanded",String($("#sidebar").classList.toggle("open"))));
document.addEventListener("click",e=>{if(innerWidth<=760&&!e.target.closest("#sidebar,#menuToggle")){$("#sidebar").classList.remove("open");menu.setAttribute("aria-expanded","false");}});
$$("[data-close-dialog]").forEach(n=>n.addEventListener("click",()=>n.closest("dialog").close()));
async function confirmDelete(title,text){const d=$("#confirmDialog");$("#confirmTitle").textContent=title;$("#confirmMessage").textContent=text;d.returnValue="cancel";d.showModal();return new Promise(resolve=>d.addEventListener("close",()=>resolve(d.returnValue==="confirm"),{once:true}));}
async function refreshStats(){try{const {data}=await api("/api/stats/");$$("[data-stat]").forEach(n=>n.textContent=data[n.dataset.stat]??"—");$(".attendance-ring")?.style.setProperty("--rate",data.attendance_rate);$("#serverStatus").classList.remove("offline");$("#serverStatus").lastChild.textContent="Máy chủ trực tuyến";}catch{$("#serverStatus").classList.add("offline");$("#serverStatus").lastChild.textContent="Mất kết nối máy chủ";}}
setInterval(refreshStats,30000);
if(page==="admin"){
 function tab(name){$$("[data-tab]").forEach(n=>{n.classList.toggle("active",n.dataset.tab===name);n.setAttribute("aria-selected",String(n.dataset.tab===name));});$$("[data-pane]").forEach(n=>n.hidden=n.dataset.pane!==name);}
 $$("[data-tab]").forEach(n=>n.addEventListener("click",()=>tab(n.dataset.tab)));
 const selected=new URLSearchParams(location.search).get("tab");if(["records","cameras"].includes(selected))tab(selected);
 function filter(){const query=$("#studentSearch").value.trim().toLocaleLowerCase("vi-VN"),value=$("#registrationFilter").value;let count=0;$$("[data-student]").forEach(n=>{n.hidden=!(n.textContent.toLocaleLowerCase("vi-VN").includes(query)&&(!value||n.dataset.registered===value));if(!n.hidden)count++;});$("#studentCount").textContent=count+" hồ sơ";$("#studentEmpty").hidden=count>0;}
 $("#studentSearch").addEventListener("input",filter);$("#registrationFilter").addEventListener("change",filter);
 $$(".edit-student").forEach(n=>n.addEventListener("click",async()=>{try{const students=(await api("/api/students/")).data,student=students.find(s=>s.id===Number(n.dataset.id));if(!student)throw new Error("Hồ sơ đã thay đổi. Hãy tải lại trang.");const form=$("#editForm");for(const key of ["id","student_id","full_name","class_name","email"])form.elements[key].value=student[key]??"";message($("#editMessage"),"");$("#editDialog").showModal();}catch(e){toast(e.message,"error");}}));
 $("#editForm").addEventListener("submit",async e=>{e.preventDefault();const form=e.currentTarget,button=$('button[type="submit"]',form),data=Object.fromEntries(new FormData(form));busy(button,true);try{await api("/api/update-student/"+data.id+"/",{method:"PUT",body:JSON.stringify(data)});location.reload();}catch(err){message($("#editMessage"),err.message,"error");busy(button,false);}});
 $$(".delete-student").forEach(n=>n.addEventListener("click",async()=>{if(!await confirmDelete("Xóa hồ sơ sinh viên?","Hồ sơ “"+n.dataset.name+"”, ảnh khuôn mặt và lịch sử điểm danh liên quan sẽ bị xóa."))return;n.disabled=true;try{await api("/api/delete-student/"+n.dataset.id+"/",{method:"DELETE"});n.closest("tr").remove();filter();refreshStats();toast("Đã xóa hồ sơ.");}catch(e){n.disabled=false;toast(e.message,"error");}}));
}
let registerStream,scanStream;
function stopTracks(stream){stream?.getTracks().forEach(t=>t.stop());}
function cameraError(e){return {NotAllowedError:"Chưa được cấp quyền camera. Vui lòng cấp quyền cho trang và thử lại.",NotFoundError:"Không tìm thấy camera. Bạn có thể tải ảnh lên để sử dụng.",NotReadableError:"Camera đang được ứng dụng khác sử dụng. Hãy đóng ứng dụng đó và thử lại."}[e.name]||e.message||"Không thể khởi động camera.";}
const cameraSelect=$("#cameraSelect"),cameraDeviceHelp=$("#cameraDeviceHelp"),refreshCameraButton=$("#refreshCameras");
const cameraPolicy=window.VistaCameraPolicy,cameraStorageKey="vista.camera.deviceId";
let cameraDevices=[];
function savedCamera(){try{return localStorage.getItem(cameraStorageKey)||"";}catch{return "";}}
function rememberCamera(id){try{localStorage.setItem(cameraStorageKey,id);}catch{/* Storage may be disabled; selection still works. */}}
function cameraBusy(on){if(cameraSelect)cameraSelect.disabled=on;if(refreshCameraButton)refreshCameraButton.disabled=on;}
function deviceMessage(text,type=""){if(cameraDeviceHelp){cameraDeviceHelp.textContent=text;cameraDeviceHelp.className=type;}}
function selectedCamera(){const explicit=cameraSelect?.value;return cameraPolicy.choose(cameraDevices,savedCamera(),explicit&&explicit!=="laptop"?explicit:"");}
function cameraStopped(){cameraBusy(false);const chosen=selectedCamera();if(chosen)deviceMessage("Thiết bị đã chọn: "+chosen.label+". Camera đang tắt.");}
async function refreshCameras(unlock=false){
 if(!cameraSelect||!navigator.mediaDevices?.enumerateDevices)return null;
 const requested=cameraSelect.value;
 let devices=await navigator.mediaDevices.enumerateDevices();
 // First-time permission can hide labels. The temporary stream is never
 // attached to a video or sent for recognition, and is always released.
 if(unlock&&devices.filter(d=>d.kind==="videoinput").every(d=>!d.label)){
  let permissionStream;
  try{permissionStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});devices=await navigator.mediaDevices.enumerateDevices();}
  finally{stopTracks(permissionStream);}
 }
 cameraDevices=devices.filter(d=>d.kind==="videoinput");
 const explicit=requested&&requested!=="laptop"?requested:"";
 const chosen=cameraPolicy.choose(cameraDevices,savedCamera(),explicit);
 const automatic=el("option","","Ưu tiên webcam laptop");automatic.value="laptop";
 cameraSelect.replaceChildren(automatic);
 for(const device of cameraDevices.filter(d=>d.label&&d.deviceId)){
  const option=el("option","",device.label+(cameraPolicy.isVirtual(device)?" · Camera ảo":""));
  option.value=device.deviceId;cameraSelect.append(option);
 }
 cameraSelect.value=chosen?.deviceId||"laptop";
 if(chosen)deviceMessage("Thiết bị đã chọn: "+chosen.label+". Dừng camera trước khi đổi thiết bị.");
 else if(cameraDevices.length&&cameraDevices.every(d=>!d.label))deviceMessage("Bấm bật camera để cấp quyền và tìm webcam laptop. Chưa gửi khung hình để nhận diện.");
 else deviceMessage("Chưa tìm thấy webcam laptop. Không tự chuyển sang Iriun. Kiểm tra camera rồi bấm tải lại.","error");
 return chosen;
}
if(cameraSelect){
 refreshCameras().catch(e=>deviceMessage(cameraError(e),"error"));
 cameraSelect.addEventListener("change",()=>{const chosen=selectedCamera();if(chosen){rememberCamera(chosen.deviceId);deviceMessage("Thiết bị đã chọn: "+chosen.label+". Bấm bật camera để sử dụng.");}});
 refreshCameraButton.addEventListener("click",async()=>{cameraBusy(true);try{await refreshCameras();}catch(e){deviceMessage(cameraError(e),"error");}finally{cameraBusy(false);}});
 navigator.mediaDevices?.addEventListener("devicechange",()=>{if(!cameraSelect.disabled)refreshCameras().catch(e=>deviceMessage(cameraError(e),"error"));});
}
async function camera(video){
 if(!navigator.mediaDevices?.getUserMedia)throw new Error("Trình duyệt chưa hỗ trợ camera. Hãy dùng http://127.0.0.1:8000/.");
 cameraBusy(true);
 const chosen=await refreshCameras(true);
 if(!chosen)throw new Error("Không tìm thấy webcam laptop. Hãy kiểm tra ACER HD User Facing trong Windows rồi tải lại danh sách camera.");
 const stream=await navigator.mediaDevices.getUserMedia(cameraPolicy.constraints(chosen));
 const track=stream.getVideoTracks()[0],actual=track.getSettings().deviceId;
 if((actual&&actual!==chosen.deviceId)||(!cameraPolicy.isVirtual(chosen)&&cameraPolicy.isVirtual({label:track.label}))){
  stopTracks(stream);throw new Error("Camera trả về không đúng thiết bị đã chọn. Hệ thống đã dừng, không chuyển sang Iriun.");
 }
 video.srcObject=stream;
 try{await video.play();}catch(e){stopTracks(stream);video.srcObject=null;throw e;}
 track.addEventListener("ended",()=>video.dispatchEvent(new Event("camera-ended")),{once:true});
 video.hidden=false;rememberCamera(chosen.deviceId);deviceMessage("Đang dùng: "+(track.label||chosen.label),"success");
 return stream;
}
function capture(video){if(!video.videoWidth)throw new Error("Camera chưa sẵn sàng. Vui lòng đợi hình ảnh xuất hiện.");const c=document.createElement("canvas"),scale=Math.min(1,1280/video.videoWidth);c.width=Math.round(video.videoWidth*scale);c.height=Math.round(video.videoHeight*scale);c.getContext("2d").drawImage(video,0,0,c.width,c.height);return c.toDataURL("image/jpeg",.88);}
function fileData(file){if(!["image/jpeg","image/png"].includes(file.type))return Promise.reject(new Error("Vui lòng chọn ảnh JPG hoặc PNG."));if(file.size>8000000)return Promise.reject(new Error("Mỗi ảnh phải nhỏ hơn 8 MB."));return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error("Không đọc được ảnh đã chọn."));reader.readAsDataURL(file);});}
if(page==="register"){
 let samples=[],saving=false;const video=$("#registerVideo");
 function render(){const grid=$("#sampleGrid");grid.replaceChildren();$("#sampleCount").textContent=samples.length;if(!samples.length)grid.append(el("p","muted","Chưa có ảnh. Chụp hoặc tải lên để bắt đầu."));samples.forEach((src,index)=>{const item=el("div","sample"),img=el("img"),remove=el("button","","×");img.src=src;img.alt="Ảnh khuôn mặt "+(index+1);remove.type="button";remove.setAttribute("aria-label","Bỏ ảnh "+(index+1));remove.disabled=saving;remove.addEventListener("click",()=>{samples.splice(index,1);render();});item.append(img,remove);grid.append(item);});}
 function stop(){stopTracks(registerStream);registerStream=null;video.srcObject=null;cameraStopped();video.hidden=true;$("#registerPlaceholder").hidden=false;$("#faceGuide").hidden=true;$("#registerCameraState").textContent="● Camera đang tắt";$("#registerCameraStart").disabled=false;$("#capturePhoto").disabled=true;$("#registerCameraStop").disabled=true;}
 $$("[data-register-mode]").forEach(n=>n.addEventListener("click",()=>{const upload=n.dataset.registerMode==="upload";$$("[data-register-mode]").forEach(b=>b.classList.toggle("active",b===n));$("#registerCameraPane").hidden=upload;$("#registerUploadPane").hidden=!upload;if(upload)stop();}));
 $("#registerCameraStart").addEventListener("click",async()=>{$("#registerCameraStart").disabled=true;try{registerStream=await camera(video);$("#registerPlaceholder").hidden=true;$("#faceGuide").hidden=false;$("#registerCameraState").textContent="● "+(registerStream.getVideoTracks()[0].label||"Webcam laptop");$("#capturePhoto").disabled=false;$("#registerCameraStop").disabled=false;}catch(e){stop();toast(cameraError(e),"error");}});
 video.addEventListener("camera-ended",()=>{stop();toast("Webcam đã ngắt kết nối. Hãy tải lại danh sách camera.","error");});
 $("#registerCameraStop").addEventListener("click",stop);
 $("#capturePhoto").addEventListener("click",()=>{if(saving)return;if(samples.length>=12){toast("Đã đủ 12 ảnh. Hãy lưu hồ sơ hoặc bỏ bớt ảnh.","error");return;}try{samples.push(capture(video));render();}catch(e){toast(e.message,"error");}});
 async function addFiles(files){if(saving)return;for(const file of files){if(samples.length>=12){toast("Tối đa 12 ảnh cho một lần đăng ký.","error");break;}try{samples.push(await fileData(file));}catch(e){toast(e.message,"error");}}render();}
 $("#faceFiles").addEventListener("change",async e=>{await addFiles(e.target.files);e.target.value="";});
 const zone=$("#uploadZone");["dragenter","dragover"].forEach(name=>zone.addEventListener(name,e=>{e.preventDefault();zone.classList.add("dragover");}));["dragleave","drop"].forEach(name=>zone.addEventListener(name,e=>{e.preventDefault();zone.classList.remove("dragover");}));zone.addEventListener("drop",e=>addFiles(e.dataTransfer.files));
 $("#clearSamples").addEventListener("click",()=>{if(!saving){samples=[];render();}});
 $("#registrationForm").addEventListener("submit",async e=>{e.preventDefault();if(saving)return;if(!samples.length){message($("#registrationMessage"),"Vui lòng chụp hoặc chọn ít nhất một ảnh.","error");return;}const form=e.currentTarget,data=Object.fromEntries(new FormData(form));data.images=[...samples];saving=true;render();busy($("#saveRegistration"),true);message($("#registrationMessage"),"Đang phân tích khuôn mặt. Lần đầu có thể mất thêm thời gian để tải mô hình.");try{const result=await api("/api/register-face/",{method:"POST",body:JSON.stringify(data)});stop();samples=[];form.reset();message($("#registrationMessage"),result.message+" Hồ sơ đã sẵn sàng điểm danh.","success");toast("Đăng ký thành công.");}catch(err){message($("#registrationMessage"),err.message,"error");}finally{saving=false;busy($("#saveRegistration"),false);render();}});
}
if(page==="schedule"){
 $$(".day-tab").forEach(n=>n.addEventListener("click",()=>{$$(".day-tab").forEach(b=>{b.classList.toggle("active",b===n);b.setAttribute("aria-selected",String(b===n));});$$("[data-day-pane]").forEach(p=>p.hidden=p.dataset.dayPane!==n.dataset.day);}));
 $("#openScheduleDialog").addEventListener("click",()=>$("#scheduleDialog").showModal());
 $("#scheduleForm").addEventListener("submit",async e=>{e.preventDefault();const button=$('button[type="submit"]',e.currentTarget),data=Object.fromEntries(new FormData(e.currentTarget));busy(button,true);try{await api("/api/schedules/",{method:"POST",body:JSON.stringify(data)});location.reload();}catch(err){message($("#scheduleMessage"),err.message,"error");busy(button,false);}});
}
if(page==="scan"||page==="session"){
 const scanner=$("#scanner"),video=$("#scanVideo"),overlay=$("#scanOverlay"),labels=$("#faceLabels"),stage=$(".camera-stage",scanner),faceOverlay=window.VistaFaceOverlay,session=scanner.dataset.session,active=scanner.dataset.active==="yes";
 let scanning=false,timer,processing=false,generation=0,imagePreview,lastRender;
 function clearAnnotations(){lastRender=null;labels.replaceChildren();overlay.hidden=true;}
 function paintAnnotations(){
  labels.replaceChildren();
  if(!lastRender||(!imagePreview&&video.hidden)){overlay.hidden=true;return;}
  const {data,width,height}=lastRender;
  const media=faceOverlay.containRect(stage.clientWidth,stage.clientHeight,width,height);
  if(!media){overlay.hidden=true;return;}
  overlay.width=width;overlay.height=height;overlay.hidden=false;
  const ctx=overlay.getContext("2d"),footerHeight=$(".camera-bottom",stage).offsetHeight;
  ctx.clearRect(0,0,width,height);ctx.lineWidth=2/media.scale;
  for(const r of data.recognized){
   const face=faceOverlay.faceRect(r.bbox,media);if(!face)continue;
   const caption=faceOverlay.caption(r),[x1,y1,x2,y2]=r.bbox;
   ctx.strokeStyle=caption.tone==="recorded"?"#b7d696":"#ebcf7e";ctx.strokeRect(x1,y1,x2-x1,y2-y1);
   const card=el("div","face-label "+caption.tone),heading=el("div","face-label-heading");
   heading.append(el("strong","face-label-name",caption.name),el("span","face-label-score",caption.score));
   card.append(heading,el("span","face-label-detail",caption.detail));card.title=caption.name+" · "+caption.score+" · "+caption.detail;
   card.style.maxWidth=Math.max(0,Math.min(290,media.width-16))+"px";labels.append(card);
   const position=faceOverlay.labelPosition(face,media,card.offsetWidth,card.offsetHeight,stage.clientHeight,footerHeight);
   card.style.left=position.left+"px";card.style.top=position.top+"px";
  }
 }
 new ResizeObserver(paintAnnotations).observe(stage);
 function stop(){scanning=false;generation++;clearTimeout(timer);stopTracks(scanStream);scanStream=null;video.srcObject=null;cameraStopped();video.hidden=true;clearAnnotations();$("#scanResults").replaceChildren();if(imagePreview){imagePreview.remove();imagePreview=null;}$("#scanPlaceholder").hidden=false;$("#scanState").textContent="Camera đã dừng";$("#scanStart").disabled=!active;$("#scanStop").disabled=true;$("#scanHint").textContent="● Camera đang tắt";message($("#scanMessage"),"Camera đã dừng. Bấm bắt đầu khi bạn sẵn sàng.");}
 function results(data,width,height){
  $("#scanLatency").textContent=(data.scan_ms??"—")+" ms / lượt xử lý";
  const list=$("#scanResults");list.replaceChildren();
  for(const r of data.recognized){const c=faceOverlay.caption(r);list.append(el("span","scan-result"+(c.tone==="warning"?" unknown":""),c.name+" · "+c.score+" · "+c.detail));}
  if(!data.faces_detected)list.append(el("span","scan-result unknown","Chưa phát hiện khuôn mặt"));
  lastRender={data,width:data.image_width||width,height:data.image_height||height};paintAnnotations();
  message($("#scanMessage"),data.faces_detected?"Đã xử lý "+data.faces_detected+" khuôn mặt. Điểm ngưỡng: "+data.threshold+"%.":"Hãy nhìn vào camera, giữ khuôn mặt rõ và đủ sáng.");
 }
 async function recognize(image,token,width,height){if(processing)return;processing=true;try{const {data}=await api("/api/recognize-face/",{method:"POST",body:JSON.stringify({image,...(session?{session_id:Number(session)}:{})})});if(token!==generation)return;results(data,width,height);await loadAttendance();}catch(e){if(token===generation){clearAnnotations();$("#scanResults").replaceChildren();message($("#scanMessage"),e.message,"error");}}finally{processing=false;}}
 async function loop(){if(!scanning)return;const token=generation;try{await recognize(capture(video),token,Math.min(1280,video.videoWidth),Math.round(video.videoHeight*Math.min(1,1280/video.videoWidth)));}catch(e){message($("#scanMessage"),e.message,"error");}if(scanning&&token===generation)timer=setTimeout(loop,1100);}
 $("#scanStart").addEventListener("click",async()=>{if(!active)return;$("#scanStart").disabled=true;if(imagePreview){imagePreview.remove();imagePreview=null;}try{scanStream=await camera(video);scanning=true;generation++;$("#scanPlaceholder").hidden=true;$("#scanState").textContent="Đang nhận diện";$("#scanStop").disabled=false;$("#scanHint").textContent="● "+(scanStream.getVideoTracks()[0].label||"Webcam laptop");message($("#scanMessage"),"Đang khởi động nhận diện…");loop();}catch(e){stop();message($("#scanMessage"),cameraError(e),"error");}});
 video.addEventListener("camera-ended",()=>{stop();message($("#scanMessage"),"Webcam đã ngắt kết nối. Hãy tải lại danh sách camera.","error");});
 $("#scanStop").addEventListener("click",stop);
 $("#scanImage").addEventListener("change",async e=>{const file=e.target.files[0];if(!file||!active||processing)return;stop();try{const image=await fileData(file);imagePreview=el("img","scan-image-preview");imagePreview.src=image;imagePreview.alt="Ảnh kiểm tra nhận diện";stage.prepend(imagePreview);await imagePreview.decode();$("#scanPlaceholder").hidden=true;$("#scanState").textContent="Đang kiểm tra ảnh";message($("#scanMessage"),"Đang phân tích ảnh. Sinh viên khớp sẽ được ghi nhận.");await recognize(image,generation);$("#scanState").textContent="Đã kiểm tra ảnh";}catch(err){message($("#scanMessage"),err.message,"error");}finally{e.target.value="";}});
 async function loadAttendance(){try{const result=await api(session?"/api/session/"+session+"/attendance/":"/api/attendance/today/"),data=result.data,present=data.filter(r=>["present","late"].includes(r.status));$("#feedCount").textContent=present.length;$("#feedUpdated").textContent=new Date().toLocaleTimeString("vi-VN");const feed=$("#attendanceFeed");feed.replaceChildren();if(!data.length){const empty=el("div","empty-state");empty.append(el("h3","","Chưa có ghi nhận"),el("p","","Kết quả điểm danh sẽ xuất hiện ở đây."));feed.append(empty);}for(const r of data){const item=el("div","feed-item"),content=el("div"),time=el("div","feed-time",r.time_in||"—");content.append(el("strong","",r.student_name),el("small","",r.student_id+" · "+(r.class_name||"Chưa có lớp")));time.append(el("span","badge "+r.status,{present:"Có mặt",late:"Đi muộn",absent:"Vắng mặt"}[r.status]||r.status));item.append(el("span","avatar",r.student_name.slice(0,1).toUpperCase()),content,time);feed.append(item);}const count=$("#sessionPresent");if(count)count.textContent=present.length;$$("[data-roster]").forEach(row=>{const r=data.find(item=>item.student_id===row.dataset.roster),state=$(".roster-state",row);state.replaceChildren(el("span","badge "+(r?.status||"neutral"),r?{present:"Có mặt",late:"Đi muộn",absent:"Vắng mặt"}[r.status]:"Chưa ghi nhận"));});if(session&&result.session.status!=="active"&&scanning)stop();}catch(e){$("#feedUpdated").textContent="Chưa đồng bộ";toast(e.message,"error");}}
 loadAttendance();setInterval(loadAttendance,5000);$("#endSessionForm")?.addEventListener("submit",stop);
}
if(page==="technology"){
 async function system(){try{const {data}=await api("/api/system/"),dl=$("#systemDetails");dl.replaceChildren();const rows=[["OpenCV",data.opencv],["Nhận diện",data.engine],["Mô hình",data.model],["Ngưỡng tương đồng",data.threshold+"%"],["Trạng thái mô hình",data.model_loaded?"Đã tải":"Chưa tải"],["Thiết bị đang dùng",data.active_providers.includes("CUDAExecutionProvider")?"GPU / CUDA":data.model_loaded?"CPU":"Chưa khởi chạy"],["Database",data.database],["Xử lý ảnh gần nhất",data.scan_ms==null?"Chưa có dữ liệu":data.scan_ms+" ms"]];for(const [key,value]of rows)dl.append(el("dt","",key),el("dd","",value));}catch(e){toast(e.message,"error");}}
 $("#refreshSystem").addEventListener("click",system);system();
}
window.addEventListener("pagehide",()=>{stopTracks(registerStream);stopTracks(scanStream);});
})();
