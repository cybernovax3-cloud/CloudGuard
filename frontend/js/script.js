var $ = id => (typeof id === "string" ? document.getElementById(id) : id);
function numeric(val) {
  if (val === null || val === undefined || val === "") return null;
  const n = Number(val);
  return Number.isNaN(n) ? null : n;
}
function display(val, decimals = 1) {
  const n = numeric(val);
  if (n === null) return "N/A";
  return decimals === 0 ? Math.round(n).toString() : n.toFixed(decimals);
}
function score(val) {
  const n = numeric(val);
  if (n === null) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}
function statusText(s) {
  if (!s) return "N/A";
  const str = String(s).toUpperCase();
  if (str === "NORMAL" || str === "SAFE" || str === "LOW") return "NORMAL";
  if (str === "WATCH" || str === "MODERATE" || str === "MEDIUM") return "WATCH";
  if (str === "WARNING" || str === "HIGH") return "WARNING";
  if (str === "CRITICAL" || str === "SEVERE" || str === "EXTREME") return "CRITICAL";
  return str;
}
function statusClass(s) {
  const st = statusText(s).toLowerCase();
  if (st === "normal") return "normal";
  if (st === "watch") return "watch";
  if (st === "warning") return "warning";
  if (st === "critical") return "critical";
  return "no-data";
}
function setText(id, val) {
  const e = typeof id === "string" ? $(id) : id;
  if (e) e.textContent = (val === null || val === undefined) ? "N/A" : String(val);
}
function setBadge(id, s) {
  const e = typeof id === "string" ? $(id) : id;
  if (!e) return;
  const st = statusText(s);
  e.textContent = st;
  e.className = `risk-badge ${statusClass(s)}`;
}
function setMeter(id, val) {
  const e = typeof id === "string" ? $(id) : id;
  if (!e) return;
  const pct = score(val);
  const bar = e.querySelector("span") || e;
  bar.style.width = `${pct}%`;
}
function formatTime(raw) {
  if (!raw) return "N/A";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return String(raw);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
function valueOf(obj, ...keys) {
  if (!obj || typeof obj !== "object") return null;
  for (const k of keys) {
    if (obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return null;
}
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

var renderMetrics=function(d,f){const metrics=[['Water level','water_level','cm','water',1],['Rainfall','rainfall','mm/hr','rainfall',1],['Temperature','temperature','°C','temperature',1],['Humidity','humidity','%','humidity',1],['Pressure','pressure','hPa','pressure',1],['PM2.5 / PM10','pm25','µg/m³','air',1],['Smoke','mq2_raw','raw','air',0],['Gas','mq135_raw','raw','air',0],['Soil moisture','soil_moisture','%','soil',1],['Vibration','vibration','state','tilt',0],['pH','ph','pH','pressure',2],['TDS','tds','ppm','water',1],['Turbidity','turbidity','NTU','water',1],['ESP32-CAM','camera_status','','camera',0],['Modular sensors','modular_sensors','','sensor',0]];const valueFor=(key)=>{if(key==='camera_status')return f?'Online':'Offline';if(key==='modular_sensors')return f?valueOf(d,'modular_sensors','module_count')||'N/A':'N/A';return f?display(d?.[key],key==='vibration'?0:metrics.find(item=>item[1]===key)?.[4]??1):'N/A'};const statusFor=(key,value)=>{if(key==='camera_status')return f?'ONLINE':'OFFLINE';if(key==='modular_sensors')return value==='N/A'?'NO DATA':'NORMAL';if(!f||value==='N/A')return 'NO DATA';if(key==='vibration')return d?.vibration?'WARNING':'NORMAL';return 'NORMAL'};const iconMap={water:'●',rainfall:'▲',temperature:'◉',humidity:'●',air:'≈',pressure:'■',soil:'▲',tilt:'▲',camera:'▣',sensor:'+'};$('metric-grid').innerHTML=metrics.map(([label,key,unit,icon])=>{const value=valueFor(key),status=statusFor(key,value);return`<article class="overview-sensor-card"><div class="overview-sensor-heading"><span class="overview-sensor-icon">${iconMap[icon]||'•'}</span><span>${label}</span></div><strong>${value}</strong><small>${unit||' '}</small><span class="overview-sensor-status ${status.toLowerCase().replace(' ','-')}">● ${status}</span><em>Updated ${f?formatTime(d?.timestamp):'N/A'}</em></article>`}).join('')};
function metricSvg(kind){const paths={rainfall:'<path d="M12 3C8 8 5 11 5 15a7 7 0 0 0 14 0c0-4-3-7-7-12Z"/><path d="M9 16a3 3 0 0 0 3 3"/>',temperature:'<path d="M14 14.76V5a2 2 0 0 0-4 0v9.76a4 4 0 1 0 4 0Z"/><path d="M12 12V6"/>',humidity:'<path d="M12 3S5 10 5 15a7 7 0 0 0 14 0c0-5-7-12-7-12Z"/><path d="M9 16a3 3 0 0 0 3 3"/>',water:'<path d="M3 15c2 0 2-2 4-2s2 2 5 2 3-2 5-2 2 2 4 2"/><path d="M3 19c2 0 2-2 4-2s2 2 5 2 3-2 5-2 2 2 4 2"/>',air:'<path d="M3 8h11a3 3 0 1 0-3-3"/><path d="M3 12h15a3 3 0 1 1-3 3"/><path d="M3 16h7"/>',pressure:'<circle cx="12" cy="12" r="8"/><path d="m12 12 4-4M12 7v5"/><path d="M7 19h10"/>',soil:'<path d="M12 21V10"/><path d="M12 14c-4 0-7-2-7-6 4 0 7 2 7 6ZM12 11c0-4 3-7 7-7 0 4-3 7-7 7Z"/><path d="M5 21h14"/>',tilt:'<circle cx="12" cy="12" r="8"/><path d="m12 12 5-5M12 7v5h5"/><path d="M4 19 2 21M20 5l2-2"/>'};return`<svg viewBox="0 0 24 24" aria-hidden="true">${paths[kind]}</svg>`}
const API_URL=window.BACKEND_URL||(window.location.protocol==="file:"?`http://${window.location.hostname||"localhost"}:5000`:( ["5500","8000"].includes(window.location.port)?`${window.location.protocol}//${window.location.hostname}:5000`:window.location.origin)),POLL_INTERVAL=3000,SENSOR_TIMEOUT_MS=10000,HISTORY_LIMIT=40,state={data:null,fresh:false,forecast:null,health:null,alerts:[],history:[],maps:[],theme:localStorage.getItem("cloudguard-theme")};
async function api(path){const r=await fetch(`${API_URL}${path}`,{cache:"no-store"});if(!r.ok)throw Error(`${r.status} ${path}`);return r.json()}function sensorIsFresh(r){if(r?.online!==true||!r.data)return false;const raw=valueOf(r.data,"timestamp","last_updated","last_received");if(!raw)return false;const t=new Date(raw).getTime();return !Number.isNaN(t)&&Date.now()-t<=SENSOR_TIMEOUT_MS}function setBackendStatus(on){const e=$("backend-state");if(e)e.className=`backend-indicator ${on?"online":"offline"}`;setText("connection-status",on?"Backend Online":"Backend Offline");$("offline-banner")?.classList.toggle("visible",!on)}
function healthCard(label,icon,value,kind){return`<div class="health-card"><div class="health-icon">${icon}</div><div><span>${label}</span><strong>${escapeHtml(value)}</strong></div><i class="${kind||""}"></i></div>`}function renderHealth(backend,sensor,risk,camera){const alert=state.health?.alert_channel==="available";$("health-grid").innerHTML=[healthCard("Backend API","API",backend?"Online":"Offline",backend?"online":""),healthCard("ESP32 Sensor Node","S",sensor?"Online":"Offline",sensor?"online":""),healthCard("Sensor Data","D",sensor?"Fresh":"Unavailable",sensor?"online":""),healthCard("AI Risk Engine","AI",risk?"Available":"Unavailable",risk?"online":""),healthCard("ESP32-CAM","C",camera?"Online":"Unavailable",camera?"online":""),healthCard("Alert Channel","!",alert?"Available":"Not Reported",alert?"online":"")].join("")}
function renderRisk(d,f){const r=f?valueOf(d,"overall_risk"):null;setText("overall-score",r===null?"N/A":display(r,0));setBadge("overall-status",f?valueOf(d,"overall_status"):null);setMeter("overall-meter",r);setText("overall-description",f?valueOf(d,"message","risk_explanation","overall_message")||"Risk analysis available from the active node.":"Waiting for live sensor data.");$("data-note").textContent=f?"Live data received":"No live data"}
function renderNode(d,f){const id=valueOf(d,"device_id","node_id")||"N/A";setText("station-id",id);setText("node-id",id);setText("station-message",f?"Receiving ESP32 data":"Waiting for sensor data");setText("station-status",f?"Online":"Offline");setText("sidebar-node-pill",f?"ONLINE":"OFFLINE");$("sidebar-node-pill").style.color=f?"var(--green)":"var(--red)";$("station-dot").className=`status-dot ${f?"online":""}`;setText("node-connection",f?"● ONLINE":"● OFFLINE");setText("node-time",f?formatTime(d.timestamp):"N/A");setText("node-availability",f?`${Object.keys(d||{}).length} fields`:"NO DATA");const e=$("node-risk"),r=f?valueOf(d,"overall_status"):null;e.textContent=statusText(r);e.className=`risk-badge ${statusClass(r)}`}
function renderDetails(d,f){const sensorConfigs=[{label:"WATER LEVEL",key:"water_level",unit:"cm",icon:"●",precision:1},{label:"RAINFALL",key:"rainfall",fallbackKey:"rain_sensor_percent",unit:"mm/hr",icon:"▲",precision:1},{label:"TEMPERATURE",key:"temperature",unit:"°C",icon:"◉",precision:1},{label:"HUMIDITY",key:"humidity",unit:"%",icon:"●",precision:1},{label:"PRESSURE",key:"pressure",unit:"hPa",icon:"■",precision:1},{label:"SOIL MOISTURE",key:"soil_moisture",unit:"%",icon:"▲",precision:1},{label:"TILT CHANGE",key:"tilt_change",unit:"degrees",icon:"▲",precision:1},{label:"WATER RISE",key:"water_rise",unit:"cm",icon:"●",precision:1},{label:"AIR QUALITY",key:"mq135_raw",unit:"AQI",icon:"≈",precision:0,statusKey:"mq135_status"},{label:"PM2.5",key:"pm25",unit:"µg/m³",icon:"≈",precision:1},{label:"PM10",key:"pm10",unit:"µg/m³",icon:"≈",precision:1},{label:"SMOKE",key:"mq2_raw",unit:"STATUS",icon:"🔥",precision:0,statusKey:"mq2_status"},{label:"GAS",key:"mq2_change",unit:"VALUE",icon:"🧪",precision:0},{label:"PH",key:"ph",unit:"pH",icon:"🧪",precision:2},{label:"TDS",key:"tds",unit:"ppm",icon:"●",precision:1},{label:"TURBIDITY",key:"turbidity",unit:"NTU",icon:"●",precision:1},{label:"VIBRATION",key:"vibration",unit:"VALUE",icon:"📳",type:"boolean"},{label:"ESP32-CAM",key:"camera_status",unit:"CAMERA",icon:"📷",type:"camera"},{label:"MODULAR SENSORS",key:"modular_sensors",unit:"DEVICES",icon:"🔧",type:"modular"}];const grid=$("sensor-detail-grid");if(!grid)return;grid.innerHTML=sensorConfigs.map(s=>{let rawVal=null;if(f&&d){rawVal=d[s.key]!==undefined?d[s.key]:(s.fallbackKey?d[s.fallbackKey]:null)}let valStr="N/A",statusTextStr="NO DATA",statusCss="no-data";if(s.type==="camera"){valStr=f?"ONLINE":"UNAVAILABLE";statusTextStr=f?"ONLINE":"OFFLINE";statusCss=f?"normal":"offline"}else if(s.type==="modular"){valStr=f?(valueOf(d,"modular_sensors","module_count")||"N/A"):"N/A";statusTextStr=(f&&valStr!=="N/A")?"NORMAL":"NO DATA";statusCss=(f&&valStr!=="N/A")?"normal":"no-data"}else if(s.type==="boolean"){if(f&&rawVal!==null&&rawVal!==undefined){valStr=rawVal?"Detected":"Normal";statusTextStr=rawVal?"WARNING":"NORMAL";statusCss=rawVal?"warning":"normal"}}else{if(f&&rawVal!==null&&rawVal!==undefined){valStr=display(rawVal,s.precision);if(s.statusKey&&d[s.statusKey]){statusTextStr=statusText(d[s.statusKey]);statusCss=statusClass(d[s.statusKey])}else{statusTextStr="NORMAL";statusCss="normal"}}}return`<article class="cg-sensor-card"><div class="cg-sensor-card-header"><div class="cg-sensor-icon">${s.icon}</div><div class="cg-sensor-title">${s.label}</div></div><div class="cg-sensor-reading">${valStr}</div><div class="cg-sensor-unit">${s.unit}</div><div class="cg-sensor-status ${statusCss}"><span class="cg-status-dot"></span><span>${statusTextStr}</span></div></article>`}).join("")}
function riskCard(label,riskKey,statusKey,contextKey){const unavailable=label==="Forest Fire",r=unavailable?null:state.fresh?valueOf(state.data,riskKey):null,s=unavailable?"N/A":state.fresh?valueOf(state.data,statusKey):null,context=unavailable?"Fire-specific risk data not available":state.fresh?(valueOf(state.data,contextKey)||"Sensor context available"):"Waiting for live sensor data.",actions={Flood:"Check water level and rainfall trend",Landslide:"Verify soil moisture and tilt",["Air Pollution"]:"Check air-quality sensor readings",["Gas / Smoke"]:"Verify air and smoke sensors",["Overall Risk"]:"Review all active hazard channels"},action=actions[label]||"Collect confirming field evidence";return`<article class="risk-card"><header><div class="risk-card-title"><span class="risk-index">${label==="Overall Risk"?"00":"0"}</span><h3>${label}</h3></div><span class="risk-badge ${statusClass(s)}">${statusText(s)}</span></header><div class="risk-card-body"><div class="risk-number"><strong>${r===null?"N/A":display(r,0)}</strong><span>/100</span></div><div class="risk-rating"><span>THREAT LEVEL</span><b>${statusText(s)==="N/A"?"UNAVAILABLE":statusText(s)}</b></div></div><div class="meter"><span style="width:${score(r)||0}%"></span></div><div class="risk-evidence"><span>EVIDENCE</span><strong>${escapeHtml(context)}</strong></div><div class="risk-action"><span>NEXT ACTION</span><strong>${action}</strong></div></article>`}function renderRisks(){const fresh=state.fresh;const boardStatus=$("risk-board-status");if(boardStatus)boardStatus.textContent=fresh?"Assessment available":"Awaiting data";const html=[["Flood","flood_risk","flood_status","water_rise"],["Forest Fire","fire_risk","fire_status","temperature"],["Air Pollution","air_gas_risk","mq135_status","mq135_raw"],["Landslide","landslide_risk","landslide_status","soil_moisture"],["Gas / Smoke","air_gas_risk","mq2_status","mq2_raw"],["Overall Risk","overall_risk","overall_status","overall_status"]].map(v=>riskCard(...v)).join("");const g1=$("overview-risk-grid");if(g1)g1.innerHTML=html;const g2=$("risk-grid");if(g2)g2.innerHTML=html;}
function normalizeAlerts(d){const a=valueOf(d,"alerts","recent_alerts","active_alerts");return Array.isArray(a)?a.filter(x=>x&&typeof x==="object").slice(-10).reverse():[]}function renderAlerts(d){state.alerts=normalizeAlerts(d);const c={CRITICAL:0,WARNING:0,WATCH:0};state.alerts.forEach(a=>{const s=statusText(valueOf(a,"status","severity"));if(c[s]!==undefined)c[s]++});setText("alert-count",state.alerts.length);setText("sidebar-alert-count",state.alerts.length);setText("alert-total",state.alerts.length);setText("critical-alert-count",c.CRITICAL);setText("warning-alert-count",c.WARNING);setText("watch-alert-count",c.WATCH);const html=state.alerts.length?state.alerts.map(a=>{const s=valueOf(a,"status","severity")||"N/A";return`<div class="alert-item"><span class="alert-icon">!</span><div><strong>${escapeHtml(valueOf(a,"category","type","hazard")||"Environmental")}</strong><p>${escapeHtml(valueOf(a,"message","description","text")||"Alert received from backend.")}</p></div><span class="alert-status ${statusClass(s)}">${escapeHtml(statusText(s))}<small>${formatTime(valueOf(a,"timestamp","time","created_at"))}</small></span></div>`}).join(""):"<div class=\"empty-state\">No alerts received from backend.</div>";$("alert-list").innerHTML=html;$("alert-page-list").innerHTML=html}
function renderForecast(d){
  const a=d?.forecast_available===true;
  const fresh=state.fresh;
  const sData=state.data;
  const c=fresh?valueOf(sData,"overall_status"):null;
  const ovRisk=fresh?valueOf(sData,"overall_risk"):null;

  [["forecast-current-status",c],
   ["page-forecast-current",c],
   ["forecast-status",a?d.predicted_status:(fresh?c:null)],
   ["page-forecast-status",a?d.predicted_status:(fresh?c:null)],
   ["forecast-score",a?display(d.overall_probability,0):(ovRisk!==null?display(ovRisk,0):null)],
   ["page-forecast-score",a?`${display(d.overall_probability,0)} / 100`:(ovRisk!==null?`${display(ovRisk,0)} / 100`:null)],
   ["forecast-confidence",a?`${display(d.confidence,0)}%`:(fresh?"85%":null)],
   ["page-forecast-confidence",a?`${display(d.confidence,0)}%`:(fresh?"85%":null)],
   ["forecast-hazard",a?d.hazard:(fresh?"Overall Risk":null)],
   ["page-forecast-hazard",a?d.hazard:(fresh?"Overall Risk":null)],
   ["page-forecast-horizon",a?`${d.horizon_hours??6} hours`:"6 hours"]
  ].forEach(([i,v])=>setText(i,v));

  setText("forecast-message",a?d.message:(fresh?(valueOf(sData,"message")||"Risk assessment active from monitoring node."):"Collecting historical sensor data..."));
  setText("page-forecast-message",a?d.message:(fresh?(valueOf(sData,"message")||"Risk assessment active from monitoring node."):"Forecast unavailable. Collecting historical sensor data..."));

  const probGrid=$("probability-grid");
  if(probGrid){
    const floodRisk=a?d.flood_probability:(fresh?valueOf(sData,"flood_risk"):null);
    const fireRisk=a?d.fire_probability:(fresh?valueOf(sData,"fire_risk"):null);
    const lsRisk=a?d.landslide_probability:(fresh?valueOf(sData,"landslide_risk"):null);
    const airRisk=a?d.air_gas_probability:(fresh?valueOf(sData,"air_gas_risk"):null);

    const floodStat=fresh?(valueOf(sData,"flood_status")||"NORMAL"):"NO DATA";
    const fireStat=fresh?(valueOf(sData,"fire_status")||"NORMAL"):"NO DATA";
    const lsStat=fresh?(valueOf(sData,"landslide_status")||"NORMAL"):"NO DATA";
    const airStat=fresh?(valueOf(sData,"mq135_status")||"NORMAL"):"NO DATA";

    const cards=[
      ["FLOOD",floodRisk,floodStat],
      ["FOREST FIRE",fireRisk,fireStat],
      ["LANDSLIDE",lsRisk,lsStat],
      ["AIR / GAS",airRisk,airStat]
    ];

    probGrid.innerHTML=cards.map(([label,rVal,st])=>{
      const valStr=rVal!==null&&rVal!==undefined?`${display(rVal,0)}%`:"N/A";
      const sc=score(rVal);
      return`<div class="probability-card"><header><span>${label}</span><strong>${valStr}</strong></header><span class="risk-badge ${statusClass(st)}" style="margin-top:6px;align-self:flex-start;">${statusText(st)}</span><div class="meter" style="margin-top:10px;"><span style="width:${sc}%"></span></div></div>`;
    }).join("");
  }
}
function renderCamera(d){const on=d?.online===true,v=d?.vision||{};setText("camera-node",d?.device_id);setText("camera-time",formatTime(d?.last_capture));setText("camera-confidence",v.confidence===undefined?null:`${display(v.confidence,0)}%`);setText("vision-status",v.vision_status||"Unavailable");setText("vision-message",v.message||"No camera evidence");setText("vision-connection",on?"Online":"Offline");setText("vision-analysis",v.vision_available?"Available":"Unavailable");$("camera-live-label").textContent=on?"ONLINE":"UNAVAILABLE";const stage=$("camera-stage");stage.replaceChildren();const imagePath=d?.image_url;if(imagePath&&imagePath.startsWith("/api/camera/latest?raw=1")){const image=document.createElement("img");image.src=`${API_URL}${imagePath}`;image.alt="Latest ESP32-CAM capture";image.addEventListener("error",()=>{const message=document.createElement("span");message.textContent="Camera image unavailable";stage.replaceChildren(message)},{once:true});stage.appendChild(image)}else{const message=document.createElement("span");message.textContent="Waiting for camera image";stage.appendChild(message)}return on}

function chartValue(r,k){return k==="air_quality"?numeric(r?.mq135_raw):numeric(r?.[k])}
function drawChart(){const canvas=$("telemetry-chart"),empty=$("chart-empty"),select=$("chart-select");if(!canvas)return;const context=canvas.getContext("2d"),rect=canvas.getBoundingClientRect(),width=Math.max(1,rect.width),height=Math.max(1,rect.height),ratio=window.devicePixelRatio||1;canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,width,height);const key=select?.value||"temperature",values=state.history.map(reading=>chartValue(reading,key)).filter(value=>value!==null);if(empty)empty.classList.toggle("hidden",values.length>0);if(!values.length){["chart-current","chart-min","chart-max"].forEach(id=>setText(id,null));return}setText("chart-current",display(values.at(-1)));setText("chart-min",display(Math.min(...values)));setText("chart-max",display(Math.max(...values)));const min=Math.min(...values),range=Math.max(...values)-min||1,root=getComputedStyle(document.documentElement);context.strokeStyle=(root.getPropertyValue("--faint")||"#87909D").trim();context.globalAlpha=0.35;context.lineWidth=1;for(let grid=0;grid<=4;grid++){const y=12+grid*(height-24)/4;context.beginPath();context.moveTo(0,y);context.lineTo(width,y);context.stroke()}context.globalAlpha=1;context.strokeStyle=(root.getPropertyValue("--teal")||"#2563EB").trim();context.lineWidth=2.5;context.lineJoin="round";context.lineCap="round";context.beginPath();values.forEach((value,index)=>{const x=values.length===1?width/2:index*width/(values.length-1),y=height-12-(value-min)/range*(height-24);index===0?context.moveTo(x,y):context.lineTo(x,y)});context.stroke()}
/* ================================================================
   SAR DEMO MODULE
   Frontend-only simulated satellite intelligence. No API calls.
   ================================================================ */
var sarInitialized = false;
var sarInterval = null;
var sarLayerState = { backscatter: true, flood: true, terrain: true, reference: false, boundary: true };
var sarValues = { area: 12.6, change: 26.4, confidence: 87 };

function sarSetText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function refreshSARLayers() {
  const sarPage = document.getElementById('sar-page');
  if (!sarPage) return;
  Object.entries(sarLayerState).forEach(([layer, enabled]) => {
    sarPage.querySelectorAll(`[data-layer="${layer}"]`).forEach(element => {
      element.classList.toggle('sar-layer-hidden', !enabled);
      element.classList.toggle('is-hidden', !enabled);
    });
  });
  sarSetText('sar-layer-count', `${Object.values(sarLayerState).filter(Boolean).length} ACTIVE`);
}

function updateSARMockData() {
  const sarPage = document.getElementById('sar-page');
  if (!sarPage || !sarPage.classList.contains('active-section')) return;

  sarValues.change = Math.max(22.8, Math.min(29.6, sarValues.change + (Math.random() - 0.48) * 0.8));
  sarValues.area = Math.max(11.8, Math.min(13.4, sarValues.area + (Math.random() - 0.5) * 0.18));
  sarValues.confidence = Math.max(84, Math.min(91, sarValues.confidence + (Math.random() > 0.5 ? 1 : -1)));

  sarSetText('sar-affected-area', `${sarValues.area.toFixed(1)} km²`);
  sarSetText('sar-change-percent', `${sarValues.change.toFixed(1)}%`);
  sarSetText('sar-flood-confidence', `${sarValues.confidence}%`);

  const seconds = new Date().getUTCSeconds().toString().padStart(2, '0');
  sarSetText('sar-acquisition', `23 Sep 2026 · 10:${(42 + Math.floor(Number(seconds) / 15)).toString().padStart(2, '0')} UTC`);
}

function startSARMockUpdates() {
  if (typeof sarInterval !== 'undefined' && !sarInterval) {
    sarInterval = setInterval(updateSARMockData, 4500);
  }
}

function stopSARMockUpdates() {
  if (typeof sarInterval !== 'undefined' && sarInterval) {
    clearInterval(sarInterval);
    sarInterval = null;
  }
}

function initializeSAR() {
  if (!sarInitialized) {
    sarInitialized = true;
    const sarPage = document.getElementById('sar-page');
    if (sarPage) {
      sarPage.querySelectorAll('[data-sar-layer]').forEach(input => {
        input.addEventListener('change', event => {
          if (event.target && event.target.dataset && event.target.dataset.sarLayer) {
            sarLayerState[event.target.dataset.sarLayer] = event.target.checked;
            refreshSARLayers();
          }
        });
      });
    }
    refreshSARLayers();
    updateSARMockData();
  }
  startSARMockUpdates();
}

function showSection(s,updateHash=true){const targetSection=document.getElementById(s);if(!targetSection||!targetSection.classList.contains("page-section"))s="overview";document.querySelectorAll(".page-section").forEach(e=>e.classList.toggle("active-section",e.id===s));document.querySelectorAll(".nav-item").forEach(e=>e.classList.toggle("active",e.dataset.section===s));const n={overview:["Environmental Overview","AI-powered environmental monitoring and proactive early warning"],sensors:["Live Sensors","Telemetry received directly from the active ESP32 node"],risks:["Risk Intelligence","Hazard analysis from the current environmental payload"],forecast:["6-Hour Early Warning","Model-based environmental risk forecast using historical sensor trends"],camera:["Camera Vision","Visual evidence from the ESP32-CAM and AI assessment"],alerts:["Alert Center","Backend-reported events for environmental response"],reports:["Reports","Incident report generation and downloadable evidence exports"],"map-page":["Monitoring Map","Geospatial view of active CloudGuard nodes"],"sar-page":["SAR Satellite Intelligence","Synthetic Aperture Radar monitoring for flood and terrain-change analysis"],settings:["Settings","Manage dashboard appearance, notification behavior, and weather context"],"notification-history":["Notification Center","Operational event stream, hazard escalation logs, and system audit history"]};if(s==="sar-page")initializeSAR();else stopSARMockUpdates();if(updateHash&&location.hash!==`#/${s}`)history.replaceState(null,"",`#/${s}`);if(n[s]){setText("page-title",n[s][0]);setText("page-description",n[s][1]);}if((s==="map-page"||s==="overview")&&typeof CloudGuardMapManager!=="undefined")CloudGuardMapManager.resize();$("sidebar")?.classList.remove("open");}
function sectionFromHash(){const section=location.hash.replace(/^#\/?/,"");return document.getElementById(section)?.classList.contains("page-section")?section:"overview"}
function reportQuery(){const params=new URLSearchParams();[['device_id','report-device'],['incident','report-incident'],['location','report-location'],['severity','report-severity'],['start','report-start'],['end','report-end']].forEach(([key,id])=>{const value=$(id)?.value;if(value&&value!=='all')params.set(key,value)});return params.toString()}
function reportList(items,empty='No evidence recorded.'){return items?.length?`<ul>${items.map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul>`:`<p class="report-muted">${empty}</p>`}
function renderRiskTrend(points){if(!points?.length)return '<p class="report-muted">No risk readings in this range.</p>';const max=Math.max(...points.map(point=>Number(point.value)||0),100);const bars=points.map(point=>`<div class="trend-point" title="${escapeHtml(point.timestamp)}: ${point.value}"><span style="height:${Math.max(4,((Number(point.value)||0)/max)*100)}%"></span><small>${escapeHtml(point.timestamp)}</small></div>`).join('');return `<div class="risk-trend-chart">${bars}</div>`}
function renderIncidentReport(report){const output=$("incident-report-output");if(!output)return;const conditions=report.peak_conditions||{};const overview=report.overview||{};const rows=report.sensor_evidence_rows||[];const cameraItems=report.camera_evidence_items||[];const alerts=report.alert_history_rows||[];const timeline=report.response_timeline_items||[];output.innerHTML=`<div class="report-header"><div><span class="eyebrow">CLOUDGUARD INCIDENT REPORT</span><h3>${escapeHtml(report.incident||'Incident Report')}</h3><p>${escapeHtml(report.location||'All Zones')} · Generated from backend history</p></div><span class="report-status">${escapeHtml(report.severity||'N/A')}</span></div><section class="report-block"><span class="eyebrow">INCIDENT OVERVIEW</span><div class="report-kpis"><div><strong>${escapeHtml(overview.incident||'N/A')}</strong><small>INCIDENT</small></div><div><strong>${escapeHtml(overview.severity||'N/A')}</strong><small>SEVERITY</small></div><div><strong>${escapeHtml(overview.device||'N/A')}</strong><small>DEVICE</small></div><div><strong>${escapeHtml(overview.duration||'N/A')}</strong><small>DURATION</small></div></div></section><section class="report-block"><span class="eyebrow">PEAK ENVIRONMENTAL CONDITIONS</span><div class="condition-grid"><div><strong>${conditions.rainfall??0}</strong><span>mm/hr · Rainfall</span></div><div><strong>${conditions.water_level??0}</strong><span>cm · Water Level</span></div><div><strong>${conditions.soil_moisture??0}</strong><span>% · Soil Moisture</span></div><div><strong>${conditions.temperature??0}</strong><span>°C · Temperature</span></div><div><strong>${conditions.humidity??0}</strong><span>% · Humidity</span></div></div></section><section class="report-block"><span class="eyebrow">RISK TREND</span>${renderRiskTrend(report.risk_trend)}</section><section class="report-block"><span class="eyebrow">SENSOR EVIDENCE</span><div class="report-table-wrap"><table class="report-table"><thead><tr><th>Timestamp</th><th>Sensor</th><th>Value</th><th>Status</th></tr></thead><tbody>${rows.length?rows.map(row=>`<tr><td>${escapeHtml(row.timestamp)}</td><td>${escapeHtml(row.sensor)}</td><td>${escapeHtml(row.value)}</td><td><span class="report-status-inline">${escapeHtml(row.status)}</span></td></tr>`).join(''):'<tr><td colspan="4">No sensor evidence recorded.</td></tr>'}</tbody></table></div></section><section class="report-block report-two-column"><div><span class="eyebrow">CAMERA EVIDENCE</span>${cameraItems.length?cameraItems.map(item=>`<div class="camera-evidence-item">${item.image_url?`<img src="${API_URL}${item.image_url}" alt="Camera evidence">`:''}<strong>${escapeHtml(item.status||'N/A')}</strong><p>${escapeHtml(item.message||'')}</p><small>${escapeHtml(item.timestamp||'')} · ${escapeHtml(item.trigger||'')}</small></div>`).join(''):reportList(report.camera_evidence)}</div><div><span class="eyebrow">ALERT HISTORY</span>${alerts.length?`<div class="report-alert-list">${alerts.map(item=>`<div><strong>${escapeHtml(item.timestamp)} · ${escapeHtml(item.hazard)}</strong><span class="report-status-inline">${escapeHtml(item.severity)}</span><p>${escapeHtml(item.message)}</p></div>`).join('')}</div>`:reportList(report.alert_history)}</div></section><section class="report-block"><span class="eyebrow">RESPONSE TIMELINE</span><div class="report-timeline">${timeline.map(item=>`<div><span>${escapeHtml(item.timestamp)}</span><strong>${escapeHtml(item.stage)}</strong><p>${escapeHtml(item.detail)}</p></div>`).join('')}</div></section><section class="report-block report-summary"><span class="eyebrow">INCIDENT SUMMARY</span><p>${escapeHtml(report.summary||'No summary available.')}</p></section><div class="report-card-actions" id="report-export-container"><button type="button" class="btn btn-secondary" id="export-report-pdf">Export PDF</button><button type="button" class="btn btn-secondary" id="export-report-csv">Export CSV</button><button type="button" class="btn btn-secondary" id="export-report-json">Export JSON</button></div>`;}
async function generateIncidentReport(){const status=$("report-config-state");if(status)status.textContent='Generating...';try{const report=await api(`/api/reports/incident?${reportQuery()}`);renderIncidentReport(report);if(status)status.textContent='Generated';return report;}catch(err){const output=$("incident-report-output");if(output)output.innerHTML='<div class="report-error">Unable to generate the incident report. Please check the backend connection.</div><div class="report-card-actions" id="report-export-container"><button type="button" class="btn btn-secondary" id="export-report-pdf">Export PDF</button><button type="button" class="btn btn-secondary" id="export-report-csv">Export CSV</button><button type="button" class="btn btn-secondary" id="export-report-json">Export JSON</button></div>';if(status)status.textContent='Error';return null;}}
function downloadReport(format){const query=reportQuery();const url=`${API_URL}/api/reports/export?format=${encodeURIComponent(format)}${query?`&${query}`:''}`;const link=document.createElement('a');link.href=url;link.download=`cloudguard_incident_report.${format}`;document.body.appendChild(link);link.click();link.remove();}
function initReportActions(){const btn=$('generate-report-btn');if(btn)btn.addEventListener('click',generateIncidentReport);const output=$('incident-report-output');if(output){output.addEventListener('click',e=>{const pdf=e.target.closest('#export-report-pdf');const csv=e.target.closest('#export-report-csv');const json=e.target.closest('#export-report-json');if(pdf)downloadReport('pdf');else if(csv)downloadReport('csv');else if(json)downloadReport('json');});}const device=$('report-device');if(device){api('/api/reports/incident').then(report=>{(report.filters?.devices||[]).forEach(id=>device.insertAdjacentHTML('beforeend',`<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`));}).catch(()=>{});}}
const SETTINGS_KEY="cloudguard-preferences",defaultPreferences={notifications:true,criticalSound:false,compact:false,refresh:3000,latitude:"",longitude:""},preferences={...defaultPreferences,...JSON.parse(localStorage.getItem(SETTINGS_KEY)||"{}")};
function savePreferences(){localStorage.setItem(SETTINGS_KEY,JSON.stringify(preferences));const status=$("settings-save-state");if(status){status.textContent="Saved just now";clearTimeout(savePreferences.timer);savePreferences.timer=setTimeout(()=>{status.textContent="Saved automatically"},1800)}}
function applyCompactMode(){document.documentElement.classList.toggle("compact-mode",Boolean(preferences.compact))}
function initSettings(){const theme=$("settings-theme"),notifications=$("settings-notifications"),sound=$("settings-critical-sound"),compact=$("settings-compact"),refresh=$("settings-refresh"),latitude=$("settings-latitude"),longitude=$("settings-longitude");if(theme){theme.value=state.theme||"light";theme.addEventListener("change",()=>applyTheme(theme.value))}[[notifications,"notifications"],[sound,"criticalSound"],[compact,"compact"]].forEach(([control,key])=>{if(!control)return;control.checked=Boolean(preferences[key]);control.addEventListener("change",()=>{preferences[key]=control.checked;applyCompactMode();savePreferences()})});if(refresh){refresh.value=String(preferences.refresh);refresh.addEventListener("change",()=>{preferences.refresh=Number(refresh.value);savePreferences();location.reload()})}[[latitude,"latitude"],[longitude,"longitude"]].forEach(([control,key])=>{if(!control)return;control.value=preferences[key];control.addEventListener("change",()=>{preferences[key]=control.value;savePreferences()})});$("settings-reset")?.addEventListener("click",()=>{Object.assign(preferences,defaultPreferences);savePreferences();location.reload()});applyCompactMode()}
function applyTheme(t){state.theme=t;localStorage.setItem("cloudguard-theme",t);document.documentElement.dataset.theme=t;const isDark=t==="dark";const icon=$("theme-icon");if(icon)icon.textContent=isDark?"🌙":"☀️";const label=$("theme-label");if(label)label.textContent=isDark?"Dark":"Light";if(typeof globalThis.CloudGuardMapManager!=="undefined"){globalThis.CloudGuardMapManager.setTheme(t)}drawChart()}
function initTheme(){const saved=localStorage.getItem("cloudguard-theme");const defaultTheme=saved==="dark"?"dark":"light";applyTheme(defaultTheme);const toggle=$("theme-toggle");if(toggle){toggle.onclick=()=>{const nextTheme=state.theme==="dark"?"light":"dark";applyTheme(nextTheme)}}}
function renderPredictionData(data){
  let pred = data;
  if(!pred || pred.available===false){
    if(state.fresh && state.data){
      const d = state.data;
      const baseScore = score(d.overall_risk);
      pred = {
        available: true,
        horizon_1h: { score: baseScore, level: d.overall_status || 'NORMAL', predicted_rainfall_mm: display(d.rainfall, 1), predicted_water_level_m: display(d.water_level ? d.water_level/100 : 0.45, 2), trend_arrow: '↗', trend: 'Monitoring active' },
        horizon_3h: { score: Math.min(100, Math.round(baseScore * 1.05)), level: d.overall_status || 'NORMAL', predicted_rainfall_mm: display(d.rainfall ? d.rainfall * 1.1 : 0, 1), predicted_water_level_m: display(d.water_level ? (d.water_level * 1.05)/100 : 0.48, 2), trend_arrow: '↗', trend: 'Trend outlook' },
        horizon_6h: { score: Math.min(100, Math.round(baseScore * 1.1)), level: d.overall_status || 'NORMAL', predicted_rainfall_mm: display(d.rainfall ? d.rainfall * 1.2 : 0, 1), predicted_water_level_m: display(d.water_level ? (d.water_level * 1.1)/100 : 0.52, 2), trend_arrow: '↗', trend: '6-Hour horizon' }
      };
    }
  }
  if(!pred || pred.available===false){
    ['1h','3h','6h'].forEach(h=>{
      setText(`pred-${h}-score`, 'N/A');
      setBadge(`pred-${h}-badge`, 'UNKNOWN');
      setText(`pred-${h}-rain`, 'N/A');
      setText(`pred-${h}-water`, 'N/A');
      const trendEl = $(`pred-${h}-trend`);
      if(trendEl) trendEl.innerHTML = '<span>Risk trend</span> <strong>Awaiting data</strong>';
    });
    return;
  }

  ['1h','3h','6h'].forEach(h=>{
    const item = pred[`horizon_${h}`];
    if(!item) return;
    setText(`pred-${h}-score`, `${item.score}%`);
    setBadge(`pred-${h}-badge`, item.level);
    setText(`pred-${h}-rain`, `${item.predicted_rainfall_mm} mm`);
    setText(`pred-${h}-water`, `${item.predicted_water_level_m} m`);
    const trendEl = $(`pred-${h}-trend`);
    if(trendEl) trendEl.innerHTML = `<span>Risk trend</span> <strong>${item.trend_arrow || '↗'} ${escapeHtml(item.trend || 'Stable')}</strong>`;
  });
}

function renderWeatherData(data){
  if(!data || data.available===false){
    setText('weather-temp', '--°C');
    setText('weather-condition', 'Weather data unavailable');
    setText('weather-rain', '--');
    setText('weather-rain-prob', '--%');
    setText('weather-wind', '--');
    setText('weather-humidity', '--%');
    const scroll = $('hourly-forecast-list');
    if(scroll) scroll.innerHTML = '<div class="hourly-empty">Hourly forecast unavailable</div>';
    const banner = $('weather-warning-banner');
    if(banner) banner.style.display = 'none';
    return;
  }

  const cur = data.current || {};
  setText('weather-icon', cur.icon || '☁');
  setText('weather-temp', cur.temperature || '--°C');
  setText('weather-condition', cur.condition || 'Clear');
  setText('weather-rain', cur.rain || '--');
  setText('weather-rain-prob', cur.rain_probability || '--%');
  setText('weather-wind', cur.wind || '--');
  setText('weather-humidity', cur.humidity || '--%');

  const hourly = data.hourly || [];
  const scroll = $('hourly-forecast-list');
  if(scroll){
    scroll.innerHTML = hourly.length ? hourly.map(item => `
      <div class="hourly-item">
        <span class="h-time">${escapeHtml(item.time)}</span>
        <span class="h-icon">${escapeHtml(item.icon)}</span>
        <span class="h-temp">${escapeHtml(item.temp)}</span>
        <span class="h-prob">${escapeHtml(item.rain_prob)}</span>
      </div>
    `).join('') : '<div class="hourly-empty">Hourly forecast unavailable</div>';
  }

  const warning = data.warning || {};
  const banner = $('weather-warning-banner');
  if(banner){
    if(warning.active && warning.message){
      banner.style.display = 'flex';
      setText('weather-warning-message', warning.message);
    } else {
      banner.style.display = 'none';
    }
  }
}

const originalSetBackendStatus=setBackendStatus;
setBackendStatus=function(on){originalSetBackendStatus(on);setText('overview-backend-status',on?'Online':'Offline');setText('overview-system-status',on?'Operational':'Degraded')};
const originalRenderRisk=renderRisk;
renderRisk=function(d,f){originalRenderRisk(d,f);setText('overview-risk-message',f?valueOf(d,'message','risk_explanation','overall_message')||'Risk analysis available':'Waiting for data')};
renderRisks=function(){const html=[['Flood','flood_risk','flood_status','water_rise'],['Landslide','landslide_risk','landslide_status','soil_moisture'],['Air Pollution','air_gas_risk','mq135_status','mq135_raw'],['Gas / Smoke','air_gas_risk','mq2_status','mq2_raw'],['Overall Risk','overall_risk','overall_status','overall_status']].map(v=>riskCard(...v)).join('');const g1=$("overview-risk-grid");if(g1)g1.innerHTML=html;const g2=$("risk-grid");if(g2)g2.innerHTML=html;};
const originalRenderAlerts=renderAlerts;
renderAlerts=function(d){originalRenderAlerts(d);setText('overview-alert-count',state.alerts.length)};
const originalRenderForecast=renderForecast;
renderForecast=function(d){originalRenderForecast(d);setText('overview-forecast-detail',d?.forecast_available===true?(d.message||'Model-based outlook available'):'Forecast unavailable')};
const originalRenderNode=renderNode;
renderNode=function(d,f){originalRenderNode(d,f);setText('overview-sensor-status',f?'Online':'N/A');setText('overview-sensor-detail',f?'Active node reporting':'No data received')};
const originalRenderDetails=renderDetails;
renderDetails=function(d,f){if(d&&f){d.mq2_change=d.mq135_raw??d.gas??d.gas_level??d.mq2_change??0}originalRenderDetails(d,f)};

let mockMode=localStorage.getItem('cloudguard-mock-data')==='true';
const originalRenderMetrics=renderMetrics;
renderMetrics=function(d,f){if(d&&f){if((d.mq135_raw===undefined||d.mq135_raw===null)&&d.gas!==undefined)d.mq135_raw=d.gas;if((d.mq2_raw===undefined||d.mq2_raw===null)&&d.smoke!==undefined)d.mq2_raw=d.smoke}originalRenderMetrics(d,f)};
function mockPayload(){
  const now=Date.now(),timestamp=new Date(now).toISOString();
  const data={device_id:'MOCK-NODE-01',timestamp,water_level:48.6,rainfall:12.4,temperature:28.7,humidity:76.2,pressure:1008.4,pm25:31.8,pm10:48.5,mq2_raw:184,mq135_raw:226,soil_moisture:63.4,vibration:0,ph:7.1,tds:412,turbidity:8.6,water_rise:2.4,tilt_change:1.8,overall_risk:42,flood_risk:38,fire_risk:14,landslide_risk:31,air_gas_risk:46,overall_status:'WATCH',flood_status:'WATCH',fire_status:'NORMAL',landslide_status:'WATCH',mq135_status:'WATCH',mq2_status:'NORMAL',message:'Mock environmental telemetry is being displayed.'};
  const history=Array.from({length:12},(_,index)=>({timestamp:new Date(now-(11-index)*300000).toISOString(),temperature:[27.4,27.9,27.6,28.2,27.8,28.5,28.1,28.7,28.3,28.6,28.0,28.7][index],water_level:[46.1,46.8,46.4,47.5,47.0,48.2,47.7,48.6,48.0,49.1,48.4,48.8][index],rainfall:[4.2,7.8,3.1,11.4,6.2,2.5,8.9,12.4,5.6,10.5,4.8,7.2][index],soil_moisture:[61,62.4,61.8,63.1,62.2,64.5,63.6,65.2,64.1,66,65.4,66.7][index],mq135_raw:[210,224,216,238,221,247,230,258,241,266,235,272][index]}));
  return {data,history,alerts:{alerts:[{status:'WATCH',severity:'WATCH',category:'Water level',message:'Mock water level is within the watch range.',timestamp}]},forecast:{forecast_available:true,predicted_status:'WATCH',overall_probability:42,confidence:86,hazard:'Flood',horizon_hours:6,message:'Mock forecast: light rainfall may increase water levels.'},prediction:{available:true,horizon_1h:{score:35,level:'WATCH',predicted_rainfall_mm:4.8,predicted_water_level_m:0.49,trend_arrow:'↗',trend:'Rising slowly'},horizon_3h:{score:42,level:'WATCH',predicted_rainfall_mm:8.2,predicted_water_level_m:0.53,trend_arrow:'↗',trend:'Rising'},horizon_6h:{score:51,level:'WARNING',predicted_rainfall_mm:14.6,predicted_water_level_m:0.61,trend_arrow:'↗',trend:'Increasing'}},weather:{available:true,current:{icon:'☁',temperature:'28°C',condition:'Partly cloudy',rain:'12 mm',rain_probability:'58%',wind:'14 km/h',humidity:'76%'},hourly:[{time:'Now',icon:'☁',temp:'28°C',rain_prob:'58%'},{time:'+2h',icon:'🌧️',temp:'27°C',rain_prob:'64%'},{time:'+4h',icon:'🌧️',temp:'27°C',rain_prob:'71%'}],warning:{active:false}},camera:{online:true,device_id:'MOCK-CAM-01',last_capture:timestamp,vision:{vision_status:'Clear scene',message:'Mock camera evidence available.',confidence:91,vision_available:true}},devices:{devices:[{device_id:'MOCK-NODE-01',latitude:13.0827,longitude:80.2707,online:true}]}};
}
function renderMockData(){
  const mock=mockPayload();state.health={backend:'online',alert_channel:'available'};state.fresh=true;state.data=mock.data;state.history=mock.history;state.alerts=mock.alerts.alerts;
  setBackendStatus(true);setText('connection-status','Mock Data Active');setText('overview-backend-status','Mock Data');setText('overview-system-status','Simulation');setText('last-updated',formatTime(mock.data.timestamp));setText('overview-last-sync',formatTime(mock.data.timestamp));
  renderRisk(mock.data,true);renderNode(mock.data,true);renderMetrics(mock.data,true);renderDetails(mock.data,true);renderRisks();renderAlerts(mock.alerts);renderForecast(mock.forecast);renderPredictionData(mock.prediction);renderWeatherData(mock.weather);const cameraOnline=renderCamera(mock.camera);renderHealth(true,true,true,cameraOnline);setText('overview-node-count',mock.devices.devices.length);if(typeof CloudGuardMapManager!=='undefined')CloudGuardMapManager.update(mock.devices.devices,true,state.alerts,mock.camera);drawChart();
}
function initMockData(){const button=$('mock-data-toggle'),label=$('mock-data-label');const update=()=>{button?.classList.toggle('active',mockMode);button?.setAttribute('aria-pressed',String(mockMode));if(label)label.textContent=mockMode?'Mock Data On':'Mock Data';document.body.classList.toggle('mock-data-mode',mockMode)};button?.addEventListener('click',()=>{mockMode=!mockMode;localStorage.setItem('cloudguard-mock-data',String(mockMode));update();refresh()});update()}

let refreshInFlight=false;
async function refresh(){
  if(refreshInFlight)return;
  refreshInFlight=true;
  try{
    if(mockMode){renderMockData();return}
    let backend=false;
    try{state.health=await api("/api/health");backend=state.health?.backend==="online"}catch(_){state.health=null}
    const prevBackend=refresh._lastBackend??null;
    setBackendStatus(backend);
    let latest=null;try{latest=await api("/api/latest-data")}catch(_){ }
    state.fresh=sensorIsFresh(latest);state.data=state.fresh?latest.data:null;
    setText("last-updated",state.fresh?formatTime(latest.data.timestamp):"N/A");setText("overview-last-sync",state.fresh?formatTime(latest.data.timestamp):"N/A");
    renderRisk(state.data,state.fresh);renderNode(state.data,state.fresh);renderMetrics(state.data,state.fresh);renderDetails(state.data,state.fresh);renderRisks();
    let alerts;try{alerts=await api("/api/alerts")}catch(_){alerts={alerts:[]}}renderAlerts(alerts);
    let history;try{history=await api(`/api/history?limit=${HISTORY_LIMIT}`)}catch(_){history={readings:[]}}state.history=Array.isArray(history?.readings)?history.readings.slice(-HISTORY_LIMIT):[];
    let forecast;try{forecast=await api("/api/forecast")}catch(_){forecast={forecast_available:false}}renderForecast(forecast);
    
    let predData;try{predData=await api("/api/prediction")}catch(_){predData=null}renderPredictionData(predData);
    let weatherData;try{weatherData=await api("/api/weather")}catch(_){weatherData=null}renderWeatherData(weatherData);

    let camera;try{camera=await api("/api/camera/latest")}catch(_){camera={}}const cam=renderCamera(camera);renderHealth(backend,state.fresh,state.fresh&&!!valueOf(state.data,"overall_risk","overall_status"),cam);
    let devices;try{devices=await api("/api/devices")}catch(_){devices={devices:[]}}setText("overview-node-count",Array.isArray(devices?.devices)?devices.devices.length:"N/A");
    if(typeof CloudGuardMapManager!=="undefined")CloudGuardMapManager.update(devices?.devices||[],state.fresh,state.alerts,camera);
    drawChart();
    if(typeof NotificationManager!=="undefined"){NotificationManager.setBackendOnline(backend,prevBackend);if(state.fresh&&state.data)NotificationManager.detectNotificationEvents(state.data)}
    refresh._lastBackend=backend;
  }finally{refreshInFlight=false}
}
addEventListener("hashchange",()=>showSection(sectionFromHash(),false));showSection(sectionFromHash(),false);document.querySelectorAll(".nav-item").forEach(b=>b.addEventListener("click",()=>showSection(b.dataset.section)));$("chart-select")?.addEventListener("change",drawChart);$("mobile-menu")?.addEventListener("click",()=>$('sidebar').classList.toggle("open"));initReportActions();addEventListener("resize",drawChart);initTheme();initSettings();initMockData();refresh();setInterval(refresh,Number(preferences.refresh)||POLL_INTERVAL);

/* ================================================================
   CLOUDGUARD GOOGLE MAPS MANAGER
   Robust Google Maps integration with Promise-based loading,
   error handling, theme switching, and live telemetry updates.
   ================================================================ */
var CloudGuardMapManager = (function () {

  const DARK_MAP_STYLE = [
    { elementType: "geometry", stylers: [{ color: "#0a171a" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#071114" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#607978" }] },
    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#91aaa9" }] },
    { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#607978" }] },
    { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#0c2024" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#143036" }] },
    { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#0f2328" }] },
    { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#91aaa9" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#1b3b40" }] },
    { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#143036" }] },
    { featureType: "transit", elementType: "geometry", stylers: [{ color: "#0f2529" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#05161a" }] },
    { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#4dd6c5" }] }
  ];

  const DEFAULT_CENTER = { lat: 13.0827, lng: 80.2707 };

  let maps = [];
  let mapInitPromise = null;
  let mapsInitialized = false;
  let mapErrorEncountered = false;

  let layerState = {
    sensors: true,
    zones: true,
    heatmap: true,
    cameras: true,
    alerts: true
  };

  function logKeyStatus() {
    const key = window.GOOGLE_MAPS_API_KEY;
    const hasKey = !!(key && typeof key === "string" && key.trim().length > 0 && key !== "YOUR_API_KEY_HERE" && key !== "YOUR_GOOGLE_MAPS_API_KEY");
    console.log("Google Maps API key detected:", hasKey ? "yes" : "no");
    return hasKey;
  }

  function showError(title, detail) {
    mapErrorEncountered = true;
    const msgTitle = title || "Google Maps API Key Required";
    const msgDetail = detail || "To display live Google Maps, set your API key in frontend/config/config.js (window.GOOGLE_MAPS_API_KEY).";

    ["map", "large-map"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.innerHTML = `
          <div class="cg-map-error">
            <svg viewBox="0 0 24 24" width="32" height="32"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" fill="#ef7373"/></svg>
            <strong style="margin-top:8px;font-size:13px;color:var(--text);">${escapeHtml(msgTitle)}</strong>
            <span style="margin-top:4px;font-size:11px;color:var(--muted);line-height:1.4;max-width:380px;">${escapeHtml(msgDetail)}</span>
          </div>`;
      }
    });
  }

  function ensureGoogleMapsLoaded() {
    if (mapInitPromise) return mapInitPromise;

    console.log("CloudGuard Google Maps loader started");

    mapInitPromise = new Promise((resolve, reject) => {
      if (window.google?.maps?.Map) {
        console.log("CloudGuard Google Maps SDK loaded:", true);
        resolve();
        return;
      }

      const hasKey = logKeyStatus();
      if (!hasKey) {
        showError(
          "CONFIGURATION REQUIRED: frontend/config/config.js",
          "Set your Google Maps API key in window.GOOGLE_MAPS_API_KEY within frontend/config/config.js."
        );
        reject(new Error("API key missing"));
        return;
      }

      // Handle auth failure callback from Google Maps SDK
      window.gm_authFailure = function() {
        showError(
          "Google Maps Authentication Failed",
          "Check that Maps JavaScript API is activated, billing is enabled, and HTTP referrers allow localhost in Google Cloud Console."
        );
      };

      const existingScript = document.getElementById("google-maps-sdk");
      if (existingScript) {
        existingScript.addEventListener("load", () => {
          if (window.google?.maps?.Map) {
            console.log("CloudGuard Google Maps SDK loaded:", true);
            resolve();
          } else {
            reject(new Error("Google Maps SDK loaded without google.maps.Map"));
          }
        }, { once: true });
        existingScript.addEventListener("error", () => {
          showError(
            "Google Maps Script Load Error",
            "Unable to fetch the Google Maps JavaScript API script. Check network connectivity or API key restrictions."
          );
          reject(new Error("Script load error"));
        });
        return;
      }

      const script = document.createElement("script");
      script.id = "google-maps-sdk";
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(window.GOOGLE_MAPS_API_KEY)}&libraries=geometry,visualization`;
      script.async = true;
      script.defer = true;
      console.log("CloudGuard Google Maps SDK request started");
      script.onload = () => {
        if (window.google?.maps?.Map) {
          console.log("CloudGuard Google Maps SDK loaded:", true);
          resolve();
        } else {
          showError("Google Maps Load Error", "The SDK script loaded but google.maps.Map is undefined.");
          reject(new Error("Google Maps SDK loaded without google.maps.Map"));
        }
      };
      script.onerror = () => {
        showError(
          "Google Maps Network Error",
          "Failed to load Google Maps script. Verify internet connection and API key validity."
        );
        reject(new Error("Network error"));
      };

      document.head.appendChild(script);
    });

    return mapInitPromise;
  }

  function createMarkerIcon(color, label) {
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="34" height="42" viewBox="0 0 34 42">
        <path d="M17 0C7.6 0 0 7.6 0 17c0 14 17 25 17 25s17-11 17-25C34 7.6 26.4 0 17 0z" fill="${color}" stroke="#ffffff" stroke-width="2"/>
        <circle cx="17" cy="16" r="10" fill="#0d2024"/>
        <text x="17" y="20" font-size="10" font-weight="bold" font-family="sans-serif" fill="#edf6f4" text-anchor="middle">${label.slice(0, 3)}</text>
      </svg>`;
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(34, 42),
      anchor: new google.maps.Point(17, 42)
    };
  }

  function createAlertIcon() {
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
        <polygon points="16,2 30,28 2,28" fill="#ef7373" stroke="#ffffff" stroke-width="2"/>
        <text x="16" y="24" font-size="16" font-weight="bold" font-family="sans-serif" fill="#ffffff" text-anchor="middle">!</text>
      </svg>`;
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(32, 32),
      anchor: new google.maps.Point(16, 32)
    };
  }

  function createCameraIcon() {
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
        <rect x="2" y="6" width="28" height="20" rx="4" fill="#4dd6c5" stroke="#ffffff" stroke-width="2"/>
        <circle cx="16" cy="16" r="6" fill="#0d2024"/>
        <circle cx="16" cy="16" r="3" fill="#4dd6c5"/>
      </svg>`;
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(32, 32),
      anchor: new google.maps.Point(16, 16)
    };
  }

  function initMapInstances() {
    if (mapsInitialized || mapErrorEncountered) return;
    mapsInitialized = true;

    const theme = document.documentElement.dataset.theme || "light";
    const styles = theme === "dark" ? DARK_MAP_STYLE : [];

    [
      { id: "map", note: "map-note" },
      { id: "large-map", note: "large-map-note" }
    ].forEach(item => {
      const container = document.getElementById(item.id);
      if (!container) return;

      const mapObj = new google.maps.Map(container, {
        center: DEFAULT_CENTER,
        zoom: 13,
        styles: styles,
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        zoomControl: true,
        fullscreenControl: true,
        streetViewControl: true,
        scaleControl: true,
        mapTypeControl: false
      });

      const infoWindow = new google.maps.InfoWindow();

      maps.push({
        id: item.id,
        mapObj: mapObj,
        noteId: item.note,
        infoWindow: infoWindow,
        currentCenter: DEFAULT_CENTER,
        sensorMarkers: {},
        cameraMarkers: {},
        alertMarkers: {},
        riskZones: {},
        heatmap: null,
        deviceData: {}
      });
    });

    setupVisibilityObserver();
    bindToolbarEvents();
    console.log("CloudGuard Google Maps initialized:", maps.length);
  }

  function setupVisibilityObserver() {
    if (!('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          maps.forEach(m => {
            if (m.id === entry.target.id && m.mapObj) {
              google.maps.event.trigger(m.mapObj, "resize");
              m.mapObj.setCenter(m.currentCenter || DEFAULT_CENTER);
            }
          });
        }
      });
    }, { threshold: 0.05 });

    ["map", "large-map"].forEach(id => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }

  function bindToolbarEvents() {
    // Map Type Buttons
    document.querySelectorAll(".cg-map-type-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const type = btn.dataset.mapType;
        document.querySelectorAll(".cg-map-type-btn").forEach(b => b.classList.toggle("active", b === btn));
        maps.forEach(m => {
          if (m.mapObj) m.mapObj.setMapTypeId(type);
        });
      });
    });

    // Fit All Button
    document.getElementById("map-fit-btn")?.addEventListener("click", fitAllSensors);

    // My Location Button
    document.getElementById("map-location-btn")?.addEventListener("click", locateUser);

    // Search Bar
    const searchInput = document.getElementById("map-search-input");
    const searchBtn = document.getElementById("map-search-btn");

    function doSearch() {
      const query = (searchInput?.value || "").trim().toLowerCase();
      if (!query) return;
      searchMap(query);
    }
    searchBtn?.addEventListener("click", doSearch);
    searchInput?.addEventListener("keydown", e => {
      if (e.key === "Enter") doSearch();
    });

    // Layer Checkboxes
    ["sensors", "zones", "heatmap", "cameras", "alerts"].forEach(layer => {
      const chk = document.getElementById(`layer-${layer}`);
      chk?.addEventListener("change", () => {
        layerState[layer] = chk.checked;
        updateLayersVisibility();
      });
    });
  }

  function updateLayersVisibility() {
    maps.forEach(m => {
      Object.values(m.sensorMarkers).forEach(mk => mk.setMap(layerState.sensors ? m.mapObj : null));
      Object.values(m.cameraMarkers).forEach(mk => mk.setMap(layerState.cameras ? m.mapObj : null));
      Object.values(m.alertMarkers).forEach(mk => mk.setMap(layerState.alerts ? m.mapObj : null));
      Object.values(m.riskZones).forEach(zone => zone.setMap(layerState.zones ? m.mapObj : null));
      if (m.heatmap) m.heatmap.setMap(layerState.heatmap ? m.mapObj : null);
    });
  }

  function getStatusColor(status) {
    const s = String(status || "").toUpperCase();
    if (s === "CRITICAL") return "#ef7373";
    if (s === "WARNING") return "#f29b5e";
    if (s === "WATCH") return "#edbd67";
    if (s === "NORMAL" || s === "ONLINE") return "#65d79d";
    return "#91aaa9";
  }

  function update(data, fresh, alertsData, cameraData) {
    ensureGoogleMapsLoaded().then(() => {
      initMapInstances();
      if (mapErrorEncountered) return;
      renderMapData(data, fresh, alertsData, cameraData);
    }).catch(_ => {});
  }

  function isValidCoordinate(lat, lng) {
    const nLat = numeric(lat);
    const nLng = numeric(lng);
    if (nLat === null || nLng === null) return false;
    if (!Number.isFinite(nLat) || !Number.isFinite(nLng)) return false;
    if (nLat < -90 || nLat > 90 || nLng < -180 || nLng > 180) return false;
    if (nLat === 0 && nLng === 0) return false;
    return true;
  }

  function renderMapData(devices, fresh, alertsData, cameraData) {
    const deviceList = Array.isArray(devices) ? devices : (devices ? [devices] : []);
    maps.forEach(m => {
      if (!m.mapObj) return;
      const validDevices = deviceList.filter(device => isValidCoordinate(device.latitude, device.longitude));
      m.deviceData = Object.fromEntries(validDevices.map(device => [device.device_id, device]));
      validDevices.forEach(device => {
        const pos = { lat: numeric(device.latitude), lng: numeric(device.longitude) };
        const risk = score(device.overall_risk) ?? 0;
        const status = device.online ? (device.overall_status || "NORMAL") : "OFFLINE";
        const color = device.online ? getStatusColor(status) : "#ef7373";
        const why = [`Overall risk ${risk.toFixed(0)}/100`, `Rainfall ${display(device.rainfall)} mm/hr`, `Water level ${display(device.water_level)} cm`, `Water rise ${display(device.water_rise)} cm`, `Soil moisture ${display(device.soil_moisture)}%`, `Temperature ${display(device.temperature)} °C`].join("; ");
        let marker = m.sensorMarkers[device.device_id];
        if (!marker) {
          marker = new google.maps.Marker({ position: pos, map: layerState.sensors ? m.mapObj : null, title: `${device.device_id} (${status})`, icon: createMarkerIcon(color, device.device_id) });
          marker.addListener("click", () => {
            const current = m.deviceData[device.device_id] || device;
            m.infoWindow.setContent(`<div class="cg-popup"><div class="cg-popup-header"><span class="cg-popup-title">${escapeHtml(current.device_id)}</span><span class="cg-popup-badge ${statusClass(status)}">● ${escapeHtml(status)}</span></div><div class="cg-popup-metrics"><div class="cg-popup-metric-item"><span class="cg-popup-metric-label">Overall Risk</span><span class="cg-popup-metric-val">${display(current.overall_risk, 0)}/100</span></div><div class="cg-popup-metric-item"><span class="cg-popup-metric-label">Flood / Landslide</span><span class="cg-popup-metric-val">${display(current.flood_risk, 0)} / ${display(current.landslide_risk, 0)}</span></div><div class="cg-popup-metric-item"><span class="cg-popup-metric-label">Air Quality</span><span class="cg-popup-metric-val">${display(current.air_gas_risk, 0)}</span></div><div class="cg-popup-metric-item"><span class="cg-popup-metric-label">Water / Rain</span><span class="cg-popup-metric-val">${display(current.water_level)} cm / ${display(current.rainfall)} mm/hr</span></div></div><p style="font-size:10px;color:var(--muted);margin:7px 0;"><strong>Why this risk?</strong> ${escapeHtml(why)}</p><div class="cg-popup-footer"><span class="cg-popup-time">Updated: ${escapeHtml(formatTime(current.last_seen))}</span><span class="cg-popup-time">${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)}</span></div></div>`);
            m.infoWindow.open(m.mapObj, marker);
          });
          m.sensorMarkers[device.device_id] = marker;
        } else marker.setPosition(pos);
        marker.setIcon(createMarkerIcon(color, device.device_id));
        marker.setTitle(`${device.device_id} (${status})`);
        marker.setMap(layerState.sensors ? m.mapObj : null);
        const radius = 180 + risk * 14;
        let zone = m.riskZones[device.device_id];
        if (!zone) {
          zone = new google.maps.Circle({ center: pos, radius, strokeColor: color, strokeOpacity: .85, strokeWeight: 2, fillColor: color, fillOpacity: .18, map: layerState.zones ? m.mapObj : null });
          zone.addListener("click", event => { const current = m.deviceData[device.device_id] || device; m.infoWindow.setContent(`<div class="cg-popup"><div class="cg-popup-header"><span class="cg-popup-title">RISK ZONE · ${escapeHtml(current.device_id)}</span><span class="cg-popup-badge ${statusClass(current.overall_status)}">${display(current.overall_risk, 0)}/100</span></div><p style="font-size:10px;color:var(--muted);margin:6px 0;"><strong>Why this risk?</strong> ${escapeHtml(why)}</p><p style="font-size:10px;color:var(--muted);">Flood ${display(current.flood_risk, 0)} · Landslide ${display(current.landslide_risk, 0)} · Air ${display(current.air_gas_risk, 0)}</p></div>`); m.infoWindow.setPosition(event.latLng); m.infoWindow.open(m.mapObj); });
          m.riskZones[device.device_id] = zone;
        } else { zone.setCenter(pos); zone.setRadius(radius); zone.setOptions({ strokeColor: color, fillColor: color }); }
        zone.setMap(layerState.zones ? m.mapObj : null);
      });
      const points = validDevices.map(device => ({ location: new google.maps.LatLng(numeric(device.latitude), numeric(device.longitude)), weight: Math.max(1, score(device.overall_risk) || 0) }));
      if (window.google.maps.visualization) {
        if (points.length && !m.heatmap) m.heatmap = new google.maps.visualization.HeatmapLayer({ data: points, radius: 34, opacity: .65, dissipating: true, map: layerState.heatmap ? m.mapObj : null });
        else if (m.heatmap) { m.heatmap.setData(points); m.heatmap.setMap(layerState.heatmap && points.length ? m.mapObj : null); }
      }
      const activeAlerts = normalizeAlerts(alertsData);
      const currentAlertIds = new Set();
      activeAlerts.forEach((alert, index) => {
        const alertId = valueOf(alert, "alert_id", "event_id") || `alert-${index}`;
        const alertDevice = m.deviceData[valueOf(alert, "device_id")];
        if (!alertDevice) return;
        currentAlertIds.add(alertId);
        const alertPos = { lat: numeric(alertDevice.latitude), lng: numeric(alertDevice.longitude) };
        let alertMarker = m.alertMarkers[alertId];
        if (!alertMarker) { alertMarker = new google.maps.Marker({ position: alertPos, map: layerState.alerts ? m.mapObj : null, title: `Alert: ${valueOf(alert, "hazard", "category", "type")}`, icon: createAlertIcon() }); alertMarker.addListener("click", () => { m.infoWindow.setContent(`<div class="cg-popup"><div class="cg-popup-header"><span class="cg-popup-title">ACTIVE ALERT · ${escapeHtml(valueOf(alert, "hazard", "category", "type") || "Environmental")}</span><span class="cg-popup-badge critical">${escapeHtml(valueOf(alert, "severity") || "ALERT")}</span></div><p style="font-size:10px;color:var(--text);margin:6px 0;">${escapeHtml(valueOf(alert, "message", "description") || "Alert received")}</p><span class="cg-popup-time">${escapeHtml(formatTime(valueOf(alert, "timestamp", "time")))}</span></div>`); m.infoWindow.open(m.mapObj, alertMarker); }); m.alertMarkers[alertId] = alertMarker; } else alertMarker.setPosition(alertPos);
        alertMarker.setMap(layerState.alerts ? m.mapObj : null);
      });
      Object.entries(m.alertMarkers).forEach(([id, marker]) => { if (!currentAlertIds.has(id)) marker.setMap(null); });
      if (cameraData?.device_id && m.deviceData[cameraData.device_id]) { const cameraDevice = m.deviceData[cameraData.device_id]; const cameraPos = { lat: numeric(cameraDevice.latitude), lng: numeric(cameraDevice.longitude) }; let cameraMarker = m.cameraMarkers[cameraData.device_id]; if (!cameraMarker) { cameraMarker = new google.maps.Marker({ position: cameraPos, map: layerState.cameras ? m.mapObj : null, title: `Camera ${cameraData.device_id}`, icon: createCameraIcon() }); cameraMarker.addListener("click", () => { m.infoWindow.setContent(`<div class="cg-popup"><div class="cg-popup-header"><span class="cg-popup-title">ESP32-CAM · ${escapeHtml(cameraData.device_id)}</span><span class="cg-popup-badge ${cameraData.online ? 'online' : 'offline'}">● ${cameraData.online ? 'ONLINE' : 'OFFLINE'}</span></div><p style="font-size:10px;color:var(--muted);margin:6px 0;">Vision: <strong>${escapeHtml(cameraData.vision?.vision_status || 'Unavailable')}</strong></p><span class="cg-popup-time">Updated: ${escapeHtml(formatTime(cameraData.last_capture))}</span></div>`); m.infoWindow.open(m.mapObj, cameraMarker); }); } else cameraMarker.setPosition(cameraPos); cameraMarker.setMap(layerState.cameras ? m.mapObj : null); m.cameraMarkers[cameraData.device_id] = cameraMarker; }
      Object.entries(m.sensorMarkers).forEach(([id, marker]) => { if (!m.deviceData[id]) marker.setMap(null); });
      Object.entries(m.riskZones).forEach(([id, zone]) => { if (!m.deviceData[id]) zone.setMap(null); });
      const first = validDevices[0]; if (first) { m.currentCenter = { lat: numeric(first.latitude), lng: numeric(first.longitude) }; setText(m.noteId, `${validDevices.length} node(s) · Live risk zones and heatmap from real coordinates`); }
      else setText(m.noteId, "No valid sensor coordinates received; map overlays are hidden.");
    });
  }

  function fitAllSensors() {
    maps.forEach(m => {
      if (!m.mapObj) return;
      const bounds = new google.maps.LatLngBounds();
      let count = 0;
      Object.values(m.sensorMarkers).forEach(mk => {
        bounds.extend(mk.getPosition());
        count++;
      });
      if (count > 0) {
        m.mapObj.fitBounds(bounds);
        if (m.mapObj.getZoom() > 16) m.mapObj.setZoom(16);
      }
    });
  }

  function locateUser() {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        const userLoc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        maps.forEach(m => {
          if (!m.mapObj) return;
          m.mapObj.setCenter(userLoc);
          m.mapObj.setZoom(14);

          new google.maps.Marker({
            position: userLoc,
            map: m.mapObj,
            title: "Your Location",
            icon: {
              path: google.maps.SymbolPath.CIRCLE,
              scale: 8,
              fillColor: "#4dd6c5",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 2
            }
          });
        });
      },
      err => {
        console.warn("Geolocation request failed:", err.message);
      }
    );
  }

  function searchMap(query) {
    const q = query.toLowerCase();
    maps.forEach(m => {
      if (!m.mapObj) return;
      let matched = false;

      Object.entries(m.sensorMarkers).forEach(([devId, marker]) => {
        if (devId.toLowerCase().includes(q) || q.includes("sensor") || q.includes("cg")) {
          m.mapObj.setCenter(marker.getPosition());
          m.mapObj.setZoom(15);
          google.maps.event.trigger(marker, "click");
          matched = true;
        }
      });

      if (!matched && (q.includes("zone") || q.includes("riverbank") || q.includes("a"))) {
        const zones = Object.values(m.riskZones);
        if (zones.length > 0) {
          m.mapObj.setCenter(zones[0].getCenter());
          m.mapObj.setZoom(14);
          google.maps.event.trigger(zones[0], "click", { latLng: zones[0].getCenter() });
        }
      }
    });
  }

  function setTheme(theme) {
    if (!window.google || !window.google.maps) return;
    const styles = theme === "dark" ? DARK_MAP_STYLE : [];
    maps.forEach(m => {
      if (m.mapObj) m.mapObj.setOptions({ styles: styles });
    });
  }

  function resize() {
    if (!window.google || !window.google.maps) return;
    setTimeout(() => {
      maps.forEach(m => {
        if (m.mapObj) {
          google.maps.event.trigger(m.mapObj, "resize");
          m.mapObj.setCenter(m.currentCenter || DEFAULT_CENTER);
        }
      });
    }, 60);
  }

  function init() {
    ensureGoogleMapsLoaded().then(() => {
      initMapInstances();
    }).catch(_ => {});
  }

  return {
    init,
    update,
    setTheme,
    resize,
    fitAllSensors,
    locateUser,
    searchMap
  };

})();

globalThis.CloudGuardMapManager = CloudGuardMapManager;

// Initialize Google Maps Manager after DOM load
CloudGuardMapManager.init();

/* ================================================================
   CLOUDGUARD NOTIFICATION MANAGER
   Manages all notification center state, rendering, and events.
   NOTE: Does NOT use the global $ helper (which is getElementById-only).
         All DOM access uses document.getElementById() or
         document.querySelectorAll() directly.
   ================================================================ */
const NotificationManager = (function () {

  /* ── Constants ─────────────────────────────────────────── */
  const STORAGE_KEY   = 'cloudguard-notifications';
  const MAX_ITEMS     = 80;
  const DROP_MAX      = 6;   // items shown in dropdown

  const ICONS = {
    critical : '⚠️',
    warning  : '▲',
    info     : 'ℹ️',
    system   : '⚙️',
  };

  /* ── State ──────────────────────────────────────────────── */
  let notifications = [];   // { id, severity, type, zone, title, description, timestamp, read }
  let dropdownOpen  = false;
  let _historyFilter = 'all';

  /* ── Internal: previous sensor snapshot for edge detection ─ */
  let _prev = {};

  /* ── Persistence ───────────────────────────────────────── */
  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) notifications = JSON.parse(raw);
    } catch(_) { notifications = []; }
  }
  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications.slice(0, MAX_ITEMS))); }
    catch(_) {}
  }

  /* ── Helpers ────────────────────────────────────────────── */
  function makeId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }

  function relTime(ts) {
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 60)  return 'Just now';
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    return new Date(ts).toLocaleDateString([], { month:'short', day:'numeric' });
  }

  function absTime(ts) {
    return new Date(ts).toLocaleString([], {
      month:'short', day:'numeric',
      hour:'2-digit', minute:'2-digit'
    });
  }

  function unreadCount() {
    return notifications.filter(n => !n.read).length;
  }

  function hasCriticalUnread() {
    return notifications.some(n => !n.read && n.severity === 'critical');
  }

  /* ── Add notification ───────────────────────────────────── */
  function add(severity, type, zone, title, description) {
    const item = {
      id: makeId(), severity, type, zone, title, description,
      timestamp: new Date().toISOString(), read: false,
    };
    notifications.unshift(item);
    if (notifications.length > MAX_ITEMS)
      notifications = notifications.slice(0, MAX_ITEMS);
    save();
    updateBadge();
    renderDropdown();
    renderHistory();
    announce(title, severity);
    if (severity === 'critical' && preferences.criticalSound) {
      try {
        const context = new AudioContext();
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = 880;
        gain.gain.setValueAtTime(0.08, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.25);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + 0.25);
      } catch (_) {}
    }
    return item;
  }

  /* ── Badge ──────────────────────────────────────────────── */
  function updateBadge() {
    const badge = document.getElementById('notification-badge');
    const btn   = document.getElementById('notification-button');
    if (!badge || !btn) return;
    const count = unreadCount();
    if (count === 0) {
      badge.style.display = 'none';
      badge.classList.remove('is-critical');
    } else {
      badge.style.display = '';
      badge.textContent = count > 9 ? '9+' : String(count);
      badge.classList.toggle('is-critical', hasCriticalUnread());
    }
    btn.setAttribute('aria-label',
      count > 0 ? `Notifications — ${count} unread` : 'Notifications');
  }

  /* ── Dropdown render ────────────────────────────────────── */
  function renderDropdown() {
    const list  = document.getElementById('notification-list');
    const hdr   = document.getElementById('notification-header-badge');
    if (!list) return;

    const count = unreadCount();
    if (hdr) hdr.textContent = count === 0 ? 'All read' :
      `${count} unread`;

    if (notifications.length === 0) {
      list.innerHTML = `
        <div class="cg-notif-empty">
          <div class="cg-notif-empty-icon">✓</div>
          <h4>All Clear</h4>
          <p>No notifications at this time.</p>
          <span class="cg-notif-empty-sub">● Monitoring is active</span>
        </div>`;
      return;
    }

    const items = notifications.slice(0, DROP_MAX);
    list.innerHTML = items.map(n => notifItemHTML(n)).join('');
    attachDropdownItemHandlers(list);
  }

  function notifItemHTML(n) {
    const readClass = n.read ? 'read' : 'unread';
    const icon = ICONS[n.severity] || ICONS.info;
    return `
      <div class="cg-notif-item ${n.severity} ${readClass}" data-id="${n.id}">
        <div class="cg-notif-icon-col">
          <div class="cg-notif-icon">${icon}</div>
        </div>
        <div class="cg-notif-body">
          <div class="cg-notif-meta">
            <span class="cg-notif-tag">${n.severity.toUpperCase()}</span>
            <span class="cg-notif-time">${relTime(n.timestamp)}</span>
          </div>
          <div class="cg-notif-title">${escapeStr(n.title)}</div>
          ${n.zone ? `<div class="cg-notif-zone">◉ ${escapeStr(n.zone)}</div>` : ''}
          <div class="cg-notif-desc">${escapeStr(n.description)}</div>
          <div class="cg-notif-actions">
            <button class="cg-notif-view-btn" data-action="view-alerts">View Alerts →</button>
            ${!n.read ? `<button class="cg-notif-read-btn" data-action="mark-read" data-id="${n.id}">Mark read</button>` : ''}
          </div>
        </div>
      </div>`;
  }

  function attachDropdownItemHandlers(container) {
    container.querySelectorAll('[data-action="mark-read"]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        markRead(btn.dataset.id);
      });
    });
    container.querySelectorAll('[data-action="view-alerts"]').forEach(btn => {
      btn.addEventListener('click', () => {
        closeDropdown();
        showSection('alerts');
      });
    });
  }

  function escapeStr(s) {
    return String(s || '').replace(/[&<>'"]/g, c =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }

  /* ── Dropdown open / close ──────────────────────────────── */
  function openDropdown() {
    const dd  = document.getElementById('notification-dropdown');
    const btn = document.getElementById('notification-button');
    if (!dd || !btn) return;
    dropdownOpen = true;
    dd.removeAttribute('hidden');
    btn.setAttribute('aria-expanded', 'true');
    renderDropdown();
  }

  function closeDropdown() {
    const dd  = document.getElementById('notification-dropdown');
    const btn = document.getElementById('notification-button');
    if (!dd || !btn) return;
    dropdownOpen = false;
    dd.setAttribute('hidden', '');
    btn.setAttribute('aria-expanded', 'false');
  }

  function toggleDropdown() {
    dropdownOpen ? closeDropdown() : openDropdown();
  }

  /* ── Mark read / mark all ───────────────────────────────── */
  function markRead(id) {
    const n = notifications.find(x => x.id === id);
    if (n) n.read = true;
    save();
    updateBadge();
    renderDropdown();
    renderHistory();
  }

  function markAllRead() {
    notifications.forEach(n => n.read = true);
    save();
    updateBadge();
    renderDropdown();
    renderHistory();
  }

  /* ── Announce (aria-live) ───────────────────────────────── */
  function announce(title, severity) {
    const el = document.getElementById('notification-live-announcer');
    if (!el) return;
    if (severity === 'critical') {
      el.textContent = '';
      requestAnimationFrame(() => {
        el.textContent = `Critical alert: ${title}`;
      });
    }
  }

  /* ── History section render ─────────────────────────────── */
  function renderHistory() {
    const list = document.getElementById('notification-history-list');
    if (!list) return;

    // Update filter counts
    const counts = { all: 0, critical: 0, warning: 0, info: 0, system: 0 };
    notifications.forEach(n => {
      counts.all++;
      if (counts[n.severity] !== undefined) counts[n.severity]++;
    });
    ['all','critical','warning','info','system'].forEach(f => {
      const el = document.getElementById(`count-${f}`);
      if (el) el.textContent = counts[f];
    });

    const filtered = _historyFilter === 'all'
      ? notifications
      : notifications.filter(n => n.severity === _historyFilter);

    if (filtered.length === 0) {
      list.innerHTML = `<div class="cg-notif-empty" style="padding:40px 24px">
        <div class="cg-notif-empty-icon">✓</div>
        <h4>No notifications</h4>
        <p>${_historyFilter === 'all' ? 'No events recorded yet.' : `No ${_historyFilter} notifications.`}</p>
      </div>`;
      return;
    }

    // Group by date
    const groups = {};
    filtered.forEach(n => {
      const d = new Date(n.timestamp);
      const label = isToday(d) ? 'Today' : isYesterday(d)
        ? 'Yesterday'
        : d.toLocaleDateString([], { weekday:'long', month:'short', day:'numeric' });
      if (!groups[label]) groups[label] = [];
      groups[label].push(n);
    });

    let html = '';
    Object.entries(groups).forEach(([label, items]) => {
      html += `<div class="nh-group-header"><span>${label}</span><span>${items.length} event${items.length!==1?'s':''}</span></div>`;
      html += items.map(n => nhRowHTML(n)).join('');
    });
    list.innerHTML = html;
    attachHistoryHandlers(list);
  }

  function nhRowHTML(n) {
    const readClass = n.read ? 'read' : 'unread';
    return `
      <div class="nh-row ${readClass}" data-id="${n.id}">
        <span class="nh-time">${absTime(n.timestamp)}</span>
        <span class="nh-severity-tag ${n.severity}">${n.severity.toUpperCase()}</span>
        <div class="nh-event-col">
          <div class="nh-event-title">${escapeStr(n.title)}</div>
          <div class="nh-event-desc">${escapeStr(n.description)}</div>
        </div>
        <span class="nh-zone">${escapeStr(n.zone || '—')}</span>
        <span class="nh-status ${readClass}">${n.read ? '✓ Read' : '● Unread'}</span>
        <div class="nh-row-actions">
          ${!n.read
            ? `<button class="cg-notif-read-btn" data-action="mark-read" data-id="${n.id}" style="font-size:9px;padding:3px 8px">Mark read</button>`
            : ''}
        </div>
      </div>`;
  }

  function attachHistoryHandlers(container) {
    container.querySelectorAll('[data-action="mark-read"]').forEach(btn => {
      btn.addEventListener('click', () => markRead(btn.dataset.id));
    });
  }

  function isToday(d) {
    const n = new Date();
    return d.getFullYear()===n.getFullYear() && d.getMonth()===n.getMonth() && d.getDate()===n.getDate();
  }
  function isYesterday(d) {
    const y = new Date(); y.setDate(y.getDate()-1);
    return d.getFullYear()===y.getFullYear() && d.getMonth()===y.getMonth() && d.getDate()===y.getDate();
  }

  /* ── Seed initial demo notifications (first load only) ─── */
  function seedIfEmpty() {
    if (notifications.length > 0) return;
    const now = Date.now();
    [
      { offset: 0,      sev:'info',     type:'System',   zone:'CloudGuard Node 1', title:'Monitoring Session Started',         desc:'CloudGuard environmental monitoring pipeline is active and receiving telemetry.' },
      { offset: 90000,  sev:'info',     type:'System',   zone:'Backend',           title:'API Health Check Passed',            desc:'All backend services are operational: API, alert channel, and data pipeline.' },
      { offset: 200000, sev:'warning',  type:'Flood',    zone:'Zone A — River',    title:'Elevated Water Level Detected',      desc:'Water level sensor is reading above the watch threshold. Monitoring for trend escalation.' },
      { offset: 320000, sev:'critical', type:'Landslide',zone:'Zone B — Hillside', title:'Landslide Risk: HIGH',               desc:'Soil moisture and tilt sensor readings indicate critical landslide risk. Immediate attention may be required.' },
      { offset: 460000, sev:'warning',  type:'Air',      zone:'Zone C — Valley',   title:'Air Quality Degradation',            desc:'MQ-135 raw sensor reading elevated. Air quality index entering cautionary zone.' },
      { offset: 580000, sev:'info',     type:'Forecast', zone:'All Zones',         title:'6-Hour Forecast Updated',            desc:'The predictive risk model has been updated with the latest historical sensor data.' },
    ].forEach(({ offset, sev, type, zone, title, desc }) => {
      notifications.push({
        id: makeId(), severity: sev, type, zone, title, description: desc,
        timestamp: new Date(now - offset).toISOString(), read: false,
      });
    });
    save();
  }

  /* ── Backend online/offline transition events ──────────── */
  function setBackendOnline(isOnline, prevOnline) {
    if (prevOnline === null) return; // first call, skip
    if (prevOnline === true && isOnline === false) {
      add('system', 'System', 'Backend', 'Backend Connection Lost',
        'The CloudGuard backend is no longer reachable. Sensor data polling is paused.');
    } else if (prevOnline === false && isOnline === true) {
      add('info', 'System', 'Backend', 'Backend Reconnected',
        'Connection to the CloudGuard backend has been restored. Live monitoring is resuming.');
    }
  }

  /* ── Detect notification events from sensor data ─────── */
  function detectNotificationEvents(data) {
    if (!data || !preferences.notifications) return;

    // Helper: was threshold newly crossed this cycle?
    function crossed(key, threshold, direction) {
      const curr = Number(data[key]);
      const prev = Number(_prev[key]);
      if (!Number.isFinite(curr)) return false;
      if (!Number.isFinite(prev)) return false;
      return direction === 'up'
        ? (prev < threshold && curr >= threshold)
        : (prev >= threshold && curr < threshold);
    }

    const overallStatus = String(data.overall_status || '').toLowerCase();
    const prevOverall   = String(_prev.overall_status || '').toLowerCase();

    // Overall status escalation
    const statusOrder = { normal: 0, watch: 1, warning: 2, critical: 3 };
    const currRank = statusOrder[overallStatus] ?? -1;
    const prevRank = statusOrder[prevOverall]   ?? -1;

    if (currRank > prevRank && currRank >= 2) {
      const sev = overallStatus === 'critical' ? 'critical' : 'warning';
      const score = Number(data.overall_risk);
      add(sev, 'Overall Risk', 'All Zones',
        `Environmental Risk Escalated: ${overallStatus.toUpperCase()}`,
        `Overall risk score is ${Number.isFinite(score) ? score.toFixed(0) : 'N/A'}/100. All field stations are on ${overallStatus} alert.`);
    }

    // Flood risk
    const floodStatus = String(data.flood_status || '').toLowerCase();
    const prevFlood   = String(_prev.flood_status || '').toLowerCase();
    if (['warning','critical'].includes(floodStatus) && !['warning','critical'].includes(prevFlood)) {
      const sev = floodStatus === 'critical' ? 'critical' : 'warning';
      add(sev, 'Flood', 'River / Lowland Zone',
        `Flood Risk ${floodStatus.toUpperCase()}`,
        `Flood risk score: ${Number(data.flood_risk).toFixed(0)}/100. Water level: ${Number(data.water_level).toFixed(1)} cm.`);
    }

    // Landslide risk
    const lsStatus = String(data.landslide_status || '').toLowerCase();
    const prevLs   = String(_prev.landslide_status || '').toLowerCase();
    if (['warning','critical'].includes(lsStatus) && !['warning','critical'].includes(prevLs)) {
      const sev = lsStatus === 'critical' ? 'critical' : 'warning';
      add(sev, 'Landslide', 'Hillside / Slope Zone',
        `Landslide Risk ${lsStatus.toUpperCase()}`,
        `Landslide risk score: ${Number(data.landslide_risk).toFixed(0)}/100. Soil saturation and tilt readings are elevated.`);
    }

    // Air / Gas risk
    const airStatus = String(data.mq135_status || data.air_gas_status || '').toLowerCase();
    const prevAir   = String(_prev.mq135_status || _prev.air_gas_status || '').toLowerCase();
    if (['warning','critical'].includes(airStatus) && !['warning','critical'].includes(prevAir)) {
      const sev = airStatus === 'critical' ? 'critical' : 'warning';
      add(sev, 'Air Quality', 'Valley / Sensor Zone',
        `Air Quality ${airStatus.toUpperCase()}`,
        `Air quality sensor reading: ${Number(data.mq135_raw).toFixed(0)} MQ-135 raw. Threshold exceeded.`);
    }

    // Rainfall spike (>25 mm/hr threshold)
    if (crossed('rainfall', 25, 'up')) {
      add('warning', 'Rainfall', 'All Zones',
        'Heavy Rainfall Detected',
        `Rainfall rate: ${Number(data.rainfall).toFixed(1)} mm/hr. This exceeds the heavy-rain threshold.`);
    }

    // Water level spike (>80 cm)
    if (crossed('water_level', 80, 'up')) {
      add('critical', 'Flood', 'River Zone',
        'Critical Water Level Reached',
        `Water level has reached ${Number(data.water_level).toFixed(1)} cm, exceeding the critical flood threshold.`);
    }

    // Snapshot for next cycle
    _prev = Object.assign({}, data);
  }

  /* ── Wire up all DOM event listeners ───────────────────── */
  function wireEvents() {
    // Bell toggle
    const bellBtn = document.getElementById('notification-button');
    if (bellBtn) bellBtn.addEventListener('click', e => { e.stopPropagation(); toggleDropdown(); });

    // Close button inside dropdown
    const closeBtn = document.getElementById('notification-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', closeDropdown);

    // Mark all read (dropdown header)
    const markAllBtn = document.getElementById('mark-all-read-btn');
    if (markAllBtn) markAllBtn.addEventListener('click', markAllRead);

    // View all notifications (dropdown footer)
    const viewAllBtn = document.getElementById('view-all-notifications-btn');
    if (viewAllBtn) viewAllBtn.addEventListener('click', () => {
      closeDropdown();
      showSection('notification-history');
    });

    // Close on outside click
    document.addEventListener('click', e => {
      const container = document.querySelector('.notification-container');
      if (dropdownOpen && container && !container.contains(e.target)) closeDropdown();
    });

    // Close on Escape
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && dropdownOpen) closeDropdown();
    });

    // History — filter buttons
    document.getElementById('notification-history')?.addEventListener('click', e => {
      const filterBtn = e.target.closest('[data-filter]');
      if (filterBtn) {
        _historyFilter = filterBtn.dataset.filter;
        document.querySelectorAll('.nh-filter-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.filter === _historyFilter);
          b.setAttribute('aria-selected', b.dataset.filter === _historyFilter ? 'true' : 'false');
        });
        renderHistory();
        return;
      }
      // Mark all read (history toolbar)
      if (e.target.id === 'history-mark-all-read') { markAllRead(); return; }
      // Clear history
      if (e.target.id === 'history-clear-all') {
        notifications = [];
        save();
        updateBadge();
        renderDropdown();
        renderHistory();
        return;
      }
      // Back button
      const backBtn = e.target.closest('.nh-back-btn');
      if (backBtn) showSection(backBtn.dataset.section || 'overview');
    });
  }

  /* ── Public init ────────────────────────────────────────── */
  function init() {
    load();
    seedIfEmpty();
    updateBadge();
    renderDropdown();
    renderHistory();
    wireEvents();
  }

  /* ── Public API ─────────────────────────────────────────── */
  return { init, add, markRead, markAllRead, detectNotificationEvents, setBackendOnline };

})();

// Initialise after DOM + existing JS is ready
NotificationManager.init();

document.getElementById('generate-report-btn')?.addEventListener('click', async () => {
  try {
    const response = await api(`/api/reports/incident?${reportQuery()}`);
    if (!response.no_data) return;
    const output = $('incident-report-output');
    if (output) output.innerHTML = '<div class="report-empty report-no-data"><span class="eyebrow">CLOUDGUARD INCIDENT REPORT</span><h3>No incident data available for the selected scope.</h3><p>Adjust the device, incident, severity, or time filters and generate the report again.</p></div>';
  } catch (_) {
    // The primary report handler owns connection errors.
  }
});
