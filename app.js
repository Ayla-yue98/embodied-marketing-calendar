(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('calendar-data').textContent);
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const categories = {brand:{name:'品牌营销',en:'Brand Marketing'},pr:{name:'公关 / PR',en:'Public Relations'},product:{name:'产品营销',en:'Product Marketing'}};
  const companies = Object.fromEntries(data.companies.map(c => [c.id,c]));
  const statuses = {pending:'原稿待核实',collected:'官网采集 · 待核实',verified:'已人工核实'};
  const todayParts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit'}).formatToParts(new Date());
  const currentYear = Number(todayParts.find(x=>x.type==='year').value);
  const currentMonth = Number(todayParts.find(x=>x.type==='month').value);
  const years = [...new Set(data.events.map(e=>e.year).filter(Boolean))].sort((a,b)=>b-a);
  const state = {company:'all',year:years.includes(currentYear)?String(currentYear):'all',month:currentMonth,view:'month',search:'',trust:'all'};
  const safeURL = url => {try {const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;}};
  function dateText(e) {
    if (e.date) return `${e.date}${e.date_basis==='publication'?' · 报道日期':''}`;
    if (e.year && e.month) return `${e.year} 年 ${e.month} 月 · 原稿月份`;
    return e.continuous?'持续动作 · 日期待确认':'年份 / 日期待确认';
  }
  function matches(e, dated=true) {
    return (state.company==='all'||e.company===state.company) &&
      (!dated || state.year==='all'||String(e.year)===state.year) &&
      (!state.search||[e.title,e.summary,companies[e.company].name,companies[e.company].en,categories[e.category].name].join(' ').toLowerCase().includes(state.search.toLowerCase())) &&
      (state.trust==='all'||(state.trust==='sourced'?e.sources.length>0:e.status===state.trust));
  }
  function events(month=null) {
    return data.events.filter(e=>e.year&&e.month&&matches(e)&&(month===null||e.month===month)).sort((a,b)=>(b.date||`${b.year}-${String(b.month).padStart(2,'0')}`).localeCompare(a.date||`${a.year}-${String(a.month).padStart(2,'0')}`)||a.title.localeCompare(b.title,'zh-CN'));
  }
  function card(e, compact=false) {
    if(compact) return `<button class="annual-event" data-event="${esc(e.id)}"><small>${esc(companies[e.company].name)} · ${esc(e.year)} · ${esc(e.date_basis==='publication'?'报道月':statuses[e.status])}</small>${esc(e.title)}</button>`;
    return `<button class="event-card" data-event="${esc(e.id)}" aria-label="查看 ${esc(e.title)} 的详情"><div class="event-meta"><span>${esc(companies[e.company].name)}</span><span class="year-tag">${esc(e.year||'日期待定')}</span></div><div class="event-title">${esc(e.title)}</div><div class="event-bottom"><span class="status ${esc(e.status)}">${esc(statuses[e.status])}</span><span>${esc(e.date_basis==='publication'?'报道月':'详情')} ↗</span></div></button>`;
  }
  function renderCompanyNav() {
    const entries=[{id:'all',name:'全部公司',en:'All companies'},...data.companies];
    $('company-nav').innerHTML=entries.map(c=>`<button class="company-button" data-company="${c.id}" aria-pressed="${state.company===c.id}"><span class="company-mark">${c.id==='all'?'ALL':esc(c.en.slice(0,2).toUpperCase())}</span><span class="company-name">${esc(c.name)}<small>${esc(c.en)}</small></span><span class="company-total">${data.events.filter(e=>c.id==='all'||e.company===c.id).length}</span></button>`).join('');
  }
  function render() {
    renderCompanyNav();
    $('year').value=state.year;
    $('view-month').setAttribute('aria-pressed',state.view==='month');
    $('view-year').setAttribute('aria-pressed',state.view==='year');
    $('months').innerHTML=Array.from({length:12},(_,i)=>`<button class="month-button" data-month="${i+1}" aria-pressed="${state.view==='month'&&state.month===i+1}" aria-label="${i+1} 月，${events(i+1).length} 条记录"><strong>${i+1}月</strong><span>${events(i+1).length} 条</span></button>`).join('');
    const shown=events(state.view==='month'?state.month:null);
    const scope=state.year==='all'?'跨年同月':`${state.year} 年`;
    const company=state.company==='all'?'全部公司':companies[state.company].name;
    $('result-title').textContent=state.view==='month'?`${state.month} 月 · ${scope}`:`全年 · ${state.year==='all'?'跨年参考':state.year+' 年'}`;
    $('result-kicker').textContent=state.view==='month'?'MONTHLY VIEW':'ANNUAL VIEW';
    $('result-summary').textContent=`${company} · ${shown.length} 条记录 · ${shown.filter(e=>e.sources.length).length} 条有出处`;
    $('data-note').textContent='原稿记录尚待核实。官网采集仅表示找到公开出处；事件事实与归类待复核。标注「报道月」的内容按官网发布日期归档。';
    if (state.view==='month') {
      $('results').innerHTML=`<div class="category-grid">${Object.entries(categories).map(([key,c])=>{const list=shown.filter(e=>e.category===key);return `<section class="category ${key}"><div class="category-head"><span class="dot"></span><h3>${c.name}<small>${c.en}</small></h3><span class="count">${list.length}</span></div>${list.length?list.map(e=>card(e)).join(''):'<div class="empty">此筛选范围暂无记录。<br>未收录不代表没有营销动作。</div>'}</section>`;}).join('')}</div>`;
    } else {
      $('results').innerHTML=`<div class="annual-wrap"><table class="annual-table"><thead><tr><th scope="col">月份</th>${Object.values(categories).map(c=>`<th scope="col">${c.name}</th>`).join('')}</tr></thead><tbody>${Array.from({length:12},(_,i)=>`<tr><td><button class="annual-month" data-month="${i+1}">${i+1} 月 ↗</button></td>${Object.keys(categories).map(cat=>{const list=shown.filter(e=>e.month===i+1&&e.category===cat);return `<td>${list.length?list.map(e=>card(e,true)).join(''):'<span class="muted">暂无记录</span>'}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    const undated=data.events.filter(e=>(!e.year||!e.month)&&matches(e,false));
    $('undated-count').textContent=`${undated.length} 条`;
    $('undated-results').innerHTML=`<div class="undated-grid">${undated.map(e=>card(e)).join('')||'<p class="muted">此筛选范围暂无记录。</p>'}</div>`;
    $('footer-count').textContent=`${data.events.length} 条记录 · ${data.events.filter(e=>e.origin==='original').length} 条来自原稿`;
  }
  function eventDetail(id) {
    const e=data.events.find(x=>x.id===id);if(!e)return;
    $('event-detail').innerHTML=`<h2 id="event-dialog-title" class="detail-title">${esc(e.title)}</h2><dl class="detail-grid"><dt>公司</dt><dd>${esc(companies[e.company].name)}</dd><dt>营销类别</dt><dd>${esc(categories[e.category].name)}${e.origin!=='original'?' · 自动归类，待复核':''}</dd><dt>时间口径</dt><dd>${esc(dateText(e))}</dd><dt>来源状态</dt><dd><span class="status ${esc(e.status)}">${esc(statuses[e.status])}</span></dd><dt>收录日期</dt><dd>${esc(e.added_at)}</dd></dl>${e.summary?`<p class="detail-note">${esc(e.summary)}</p>`:''}<p class="detail-note">${esc(e.notes||'公司官网披露的动作。量产、销量、订单与领先性表述属于公司口径。')}</p><h3>出处</h3>${e.sources.length?`<ul class="source-list">${e.sources.map(s=>{const href=safeURL(s.url);return `<li>${href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.publisher)} ↗</a>`:esc(s.title||s.publisher)}<small>${esc(s.publisher)}${s.published_at?' · '+esc(s.published_at):''}${s.kind==='listing'?' · 官网列表，日期为列表标注':''}</small></li>`;}).join('')}</ul>`:'<p class="muted">原稿未附来源链接，暂不可视为已核实事实。</p>'}`;
    $('event-dialog').showModal();
  }
  function about() {
    const a=data.automation;
    const runs=data.runs||[];
    $('about-content').innerHTML=`<p>每月补充七家公司公开发布的营销动作，保留历史年份，并记录采集时间和出处。</p><h3>月度更新</h3><p>${esc(a.state)} · ${esc(a.cadence)}（北京时间）。${a.enabled?'由线上定时任务采集官网新闻并重新发布页面。':'完成网站发布与定时任务配置后启用。'} 官网采集自动归类；原稿核实和事件日期校正需另行审核。</p><h3>三类口径</h3><p><b>品牌营销：</b>面向大众、用户与开发者心智，包含演出、赛事、联名、互动展示与内容传播。<br><b>公关 / PR：</b>面向信任与信用，包含合作、融资、获奖、认证、高管发声与组织变化。<br><b>产品营销：</b>面向卖点与转化，包含发布、预售、实测、量产、交付与渠道。</p><h3>可信度与时间</h3><p>「原稿待核实」为附件导入内容；「官网采集」为公开官网记录，事实与自动归类尚待复核；「已人工核实」需逐条审阅并补充依据。官网日期是发布日期，不能直接等同于事件发生日。公司披露的销量、订单、领先性表述不代表独立验证。</p><h3>最近采集</h3>${runs.length?runs.slice(0,6).map(r=>`<div class="run-item">${esc(r.at.slice(0,10))} · 新增 ${r.added} 条<small>${esc(r.status)} · ${r.ok_sources}/${r.total_sources} 个入口成功${r.window?' · 检索 '+esc(r.window):''}</small>${(r.sources||[]).map(s=>`<div class="source-health"><span>${esc(companies[s.company]?.name||s.company)}</span><span>${esc(s.state)} · ${s.count??0} 条${s.error?' · '+esc(s.error):''}</span></div>`).join('')}</div>`).join(''):'<p>尚未运行线上采集任务。</p>'}<h3>原稿导入</h3><p>${esc(data.import.filename)}<br>${esc(data.import.imported_at)} 导入 ${data.import.records} 条公司明细。原稿内的行业判断未作为已核实结论发布。</p>`;
    $('about-dialog').showModal();
  }
  function exportCSV() {
    const rows=events(state.view==='month'?state.month:null);
    const q=s=>{s=String(s??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
    const header=['公司','营销类别','标题','年份','月份','日期','时间口径','来源状态','出处'];
    const csv='\ufeff'+[header,...rows.map(e=>[companies[e.company].name,categories[e.category].name,e.title,e.year,e.month,e.date,e.date_basis,statuses[e.status],e.sources.map(s=>s.url).join(' | ')])].map(r=>r.map(q).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
    const a=document.createElement('a');a.href=url;a.download=`具身营销日历_${state.year}_${state.view==='month'?state.month+'月':'全年'}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  $('year').innerHTML='<option value="all">跨年同月参考</option>'+years.map(y=>`<option value="${y}">${y} 年</option>`).join('');
  $('updated-date').textContent=data.updated_at.slice(0,10).replace(/-/g,'.');
  $('automation-state').textContent=data.automation.state;
  document.addEventListener('click',ev=>{
    const co=ev.target.closest('[data-company]');if(co){state.company=co.dataset.company;render();return;}
    const mo=ev.target.closest('[data-month]');if(mo){state.month=Number(mo.dataset.month);state.view='month';render();return;}
    const record=ev.target.closest('[data-event]');if(record)eventDetail(record.dataset.event);
  });
  $('year').addEventListener('change',e=>{state.year=e.target.value;render();});
  $('trust').addEventListener('change',e=>{state.trust=e.target.value;render();});
  $('search').addEventListener('input',e=>{state.search=e.target.value.trim();render();});
  $('view-month').addEventListener('click',()=>{state.view='month';render();});
  $('view-year').addEventListener('click',()=>{state.view='year';render();});
  $('export').addEventListener('click',exportCSV);
  $('about-button').addEventListener('click',about);
  $('close-event').addEventListener('click',()=>$('event-dialog').close());
  $('close-about').addEventListener('click',()=>$('about-dialog').close());
  [$('event-dialog'),$('about-dialog')].forEach(d=>d.addEventListener('click',ev=>{if(ev.target===d){const r=d.getBoundingClientRect();if(ev.clientX<r.left||ev.clientX>r.right||ev.clientY<r.top||ev.clientY>r.bottom)d.close();}}));
  render();
})();
