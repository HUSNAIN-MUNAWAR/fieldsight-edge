export const demoDetection = (id: string, index = 1) => ({
  id,
  media_id: `img-${String(index).padStart(3,'0')}`,
  asset_id: `asset-${String(index).padStart(3,'0')}`,
  label: ['Damaged panel','Vegetation obstruction','Hotspot-risk marker','Frame corrosion','Soiling'][index % 5],
  severity: ['critical','high','high','medium','medium'][index % 5],
  confidence: [.93,.79,.84,.72,.68][index % 5],
  review_state: index % 3 === 0 ? 'verified' : 'pending',
  model_version: 'vision-solar-1.4.2',
  created_at: '2026-07-07T09:42:00+00:00',
  bbox: {x: 16 + index*4, y: 18 + index*3, w: 29, h: 24},
  asset: {id:`asset-${String(index).padStart(3,'0')}`,name:`PV-${String(index).padStart(3,'0')}`,asset_type:'PV module row',site_id:'site-alpha-a',lat:33.618,lng:73.063},
  media: {id:`img-${String(index).padStart(3,'0')}`,site_id:'site-alpha-a',source:'Drone · Mavic 3E',lat:33.618,lng:73.063,checksum:'sha256:syntheticdemo'},
});

export function initialScreenData(screen: string): any {
  const findings = Array.from({length: 14},(_,i)=>demoDetection(`det-${String(i+1).padStart(3,'0')}`,i+1));
  if(screen==='dashboard') return {kpis:{active_projects:3,new_findings:47,critical_defects:4,pending_review:24,open_work_orders:22,sync_queue:47},priority:findings.slice(0,7),recent_uploads:Array.from({length:6},(_,i)=>({id:`img-${String(i+1).padStart(3,'0')}`,source:i%2?'Edge · FS-CAM-02':'Drone · Mavic 3E',captured_at:'2026-07-07T09:42:00+00:00'})),projects:[],devices:[],work_orders:[],insight:'Since the previous Alpha flight, 6 new potential issues were found. Two require immediate review before the afternoon maintenance window.'};
  if(screen==='map') return {sites:[],assets:Array.from({length:65},(_,i)=>({id:`asset-${i+1}`})),detections:findings,flight_path:[]};
  if(screen==='review'||screen==='defects') return findings;
  if(screen==='assets') return {asset:{id:'asset-015',name:'PV-015',asset_type:'PV module row',site_id:'site-alpha-a',risk_score:74},media:[{id:'img-015'},{id:'img-021'}],timeline:[{date:'2026-07-07',event:'Inspection capture',source:'Drone · Mavic 3E'},{date:'2026-07-06',event:'AI finding verified',source:'Ayesha Malik'},{date:'2026-07-01',event:'Baseline capture',source:'Drone · Mavic 3E'}],work_orders:[{id:'wo-015',severity:'critical',title:'Remediate damaged panel — PV-015',assignee:'Field Ops North',sla_due:'2026-07-10'}]};
  if(screen==='devices') return {devices:[{id:'edge-01',name:'FS-DRONE-ALPHA',site:'Alpha East Array',state:'online',battery:86,cpu:42,storage:61,last_sync:'2m ago',model:'vision-solar-1.4.2',pending:0},{id:'edge-02',name:'FS-CAM-02',site:'Alpha Inverter Yard',state:'syncing',battery:74,cpu:58,storage:72,last_sync:'syncing now',model:'vision-solar-1.4.2',pending:18},{id:'edge-03',name:'FS-DRONE-NORTH',site:'North Corridor 02',state:'offline',battery:31,cpu:0,storage:83,last_sync:'46m ago',model:'vision-solar-1.3.8',pending:26},{id:'edge-04',name:'FS-ROOF-EAST',site:'East Campus Roof',state:'online',battery:100,cpu:19,storage:39,last_sync:'6m ago',model:'vision-solar-1.4.2',pending:0},{id:'edge-05',name:'FS-UTILITY-01',site:'North Corridor 01',state:'online',battery:67,cpu:37,storage:46,last_sync:'12m ago',model:'vision-solar-1.4.2',pending:3}],events:[{id:'a1',action:'Completed offline queue synchronization',actor:'FS-DRONE-NORTH',metadata:'26 jobs uploaded',at:'2026-07-07T09:30:00+00:00'},{id:'a2',action:'Queued 18 captures while offline',actor:'FS-CAM-02',metadata:'Connectivity intermittent',at:'2026-07-07T09:18:00+00:00'}]};
  if(screen==='models') return {models:[{id:'model-1.3.8',version:'vision-solar-1.3.8',status:'retired',precision:.84,recall:.79,deployed_to:1},{id:'model-1.4.2',version:'vision-solar-1.4.2',status:'production',precision:.91,recall:.88,deployed_to:4},{id:'model-1.5.0',version:'vision-solar-1.5.0-rc1',status:'validation',precision:.94,recall:.89,deployed_to:0}],confidence_distribution:[{range:'0.50–0.60',count:9},{range:'0.60–0.70',count:24},{range:'0.70–0.80',count:51},{range:'0.80–0.90',count:46},{range:'0.90–1.00',count:25}],evaluations:[{dataset:'solar-demo-v3',date:'2026-07-05',precision:.91,recall:.88},{dataset:'solar-hard-negatives-v2',date:'2026-06-28',precision:.89,recall:.86}]};
  return {title:'Solar Farm Alpha — Inspection Report',summary:'Drone coverage reached 94% across Alpha East Array. The review queue contains two high-impact findings that should be dispatched before the afternoon maintenance window.',statistics:{assets:84,media:132,detections:37,verified:21,critical:4,work_orders:11},recommendations:['Prioritize panel damage at PV-015 and PV-031.','Schedule vegetation clearance for Zone C within 48 hours.','Reinspect inverter yard after remediation closure.'],findings:findings.slice(0,4)};
}
