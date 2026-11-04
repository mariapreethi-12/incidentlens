const $ = id => document.getElementById(id);
let state = null, pending = false;
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {'database-lock':'Database contention','payment-outage':'Payment dependency outage','inventory-latency':'Inventory latency','bad-release':'Checkout release regression','retry-storm':'Retry amplification',healthy:'No failure detected','insufficient-evidence':'Insufficient evidence'};
function notify(message) { $('notice').textContent = message; $('notice').hidden = !message; }
function render(data) {
  state = data;
  if (!$('scenario').options.length) {
    for (const [key, value] of Object.entries(data.scenarios)) { const option = document.createElement('option'); option.value = key; option.textContent = value.title; $('scenario').append(option); }
    $('scenario').value = data.scenario;
  }
  $('scenario-description').textContent = data.scenarios[$('scenario').value].description;
  $('run-id').textContent = data.generation;
  $('model-note').textContent = data.model_configured ? `Model available: ${data.model}. Model modes make paid API requests.` : 'Rules baseline is available. Set OPENAI_API_KEY and OPENAI_MODEL on the server to enable AI.';
  for (const option of $('mode').options) option.disabled = option.value !== 'baseline' && !data.model_configured;
  const busy = pending || data.busy;
  ['inject','probe','investigate','scenario','mode'].forEach(id => $(id).disabled = busy);
  $('recover').disabled = busy || !data.report || !!data.recovery || ['healthy','insufficient-evidence'].includes(data.report.diagnosis.category);
  $('metrics').innerHTML = data.metrics.map(m => `<article class="metric"><div class="metric-top"><span>${escapeHtml(m.service.toUpperCase())}</span><span class="status ${m.errors ? 'bad':''}">${m.errors ? '● DEGRADED':'● OBSERVED'}</span></div><div class="metric-value">${m.p95_ms.toFixed(1)}<small>ms p95</small></div><div class="metric-foot">${m.requests} requests &nbsp; / &nbsp; ${Math.round(m.error_rate*100)}% errors</div></article>`).join('');
  data.metrics.forEach(m => { const node = $(`node-${m.service}`); node.classList.toggle('error', m.errors > 0); node.classList.toggle('slow', !m.errors && m.p95_ms > 150); });
  $('events').innerHTML = [...data.events].reverse().map(e => `<tr id="${escapeHtml(e.id)}"><td>${new Date(e.timestamp*1000).toLocaleTimeString()}</td><td>${escapeHtml(e.service)}</td><td><span class="status ${e.status>=500?'bad':''}">${e.status}</span></td><td>${e.duration_ms.toFixed(1)} ms</td><td>${escapeHtml(e.message)}<small>${escapeHtml(e.id)} / trace ${escapeHtml(e.trace_id)}</small></td></tr>`).join('');
  $('recovery-result').textContent = data.recovery ? (data.recovery.healthy ? `✓ Recovery verified: ${data.recovery.probes}/5 fresh checkouts succeeded.` : 'Recovery verification failed. Inspect new evidence.') : '';
  const report = data.report;
  if (!report) {
    $('investigation-body').className = 'empty';
    $('investigation-body').innerHTML = '<div class="empty-symbol">⌕</div><h3>The answer is in the evidence.</h3><p>Inject a failure, then investigate its logs, metrics, traces, and deployment changes.</p>';
    return;
  }
  const d = report.diagnosis;
  $('investigation-body').className = '';
  $('investigation-body').innerHTML = `<div class="report-summary"><div class="label">${report.mode==='baseline'?'DETERMINISTIC BASELINE':'MODEL INVESTIGATION'}</div><h3>${escapeHtml(titles[d.category])}</h3><p>${escapeHtml(d.summary)}</p><div class="citations">${d.evidence_ids.map(id=>`<button class="citation" data-evidence="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join('')}</div></div><div class="report-meta">${report.elapsed_ms} ms investigation · ${report.steps.length} tool calls · ${report.usage.input_tokens + report.usage.output_tokens} model tokens</div><div class="label">RECOMMENDED NEXT STEPS</div><ol class="report-list">${d.next_steps.map(s=>`<li>${escapeHtml(s)}</li>`).join('')}</ol><div class="label">TOOL EXECUTION TRACE</div>${report.steps.map((s,i)=>`<details class="tool-step"><summary>${String(i+1).padStart(2,'0')} &nbsp; ${escapeHtml(s.tool)}() <span class="muted">→ ${s.records} records</span></summary><pre>${escapeHtml(JSON.stringify(s.evidence,null,2))}</pre></details>`).join('')}<p class="report-meta">Citations verify record existence, not causal correctness. Diagnosis describes the pre-recovery snapshot.</p>`;
}
async function refresh() { const response = await fetch('/api/state'); if (!response.ok) throw new Error('Could not load the laboratory'); render(await response.json()); }
async function action(path, body, label) {
  if (pending) return;
  pending = true; notify(''); render(state);
  const old = $('investigate').textContent;
  $('investigate').textContent = label;
  try { const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const data = await response.json(); if (!response.ok) throw new Error(data.error); }
  catch(error) { notify(error.message); }
  finally { pending = false; $('investigate').textContent = old; try { await refresh(); } catch(error) { notify(error.message); } }
}
$('scenario').addEventListener('change',()=>{ if(state) $('scenario-description').textContent=state.scenarios[$('scenario').value].description; });
$('inject').addEventListener('click',()=>action('/api/scenario',{scenario:$('scenario').value},'Collecting traffic…'));
$('probe').addEventListener('click',()=>action('/api/probe',{},'Collecting traffic…'));
$('investigate').addEventListener('click',()=>action('/api/investigate',{mode:$('mode').value},'Investigating…'));
$('recover').addEventListener('click',()=>action('/api/recover',{generation:state.generation},'Verifying recovery…'));
$('investigation-body').addEventListener('click', event => {
  const button=event.target.closest('[data-evidence]'); if(!button)return;
  const id=button.dataset.evidence, row=document.getElementById(id);
  if(row) { row.scrollIntoView({behavior:'smooth',block:'center'});row.classList.add('highlight');setTimeout(()=>row.classList.remove('highlight'),2000); }
  else { const record=state.report.steps.flatMap(s=>s.evidence).find(e=>e.id===id); if(record) { notify(`${id}: ${JSON.stringify(record)}`); $('notice').scrollIntoView({behavior:'smooth',block:'center'}); } }
});
refresh().catch(error=>notify(error.message));
setInterval(()=>{ if(!pending) refresh().catch(error=>notify(error.message)); },5000);
