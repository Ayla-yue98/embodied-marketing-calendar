"""Collect dated official headlines and rebuild the calendar, without API keys.

Publication date is always separate from event date. Collected headlines stay
unverified. Previous events survive failed fetches and missing articles.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen
import argparse, hashlib, json, os, re, tempfile
from build import build

ROOT=Path(__file__).resolve().parent
TZ=timezone(timedelta(hours=8))
DATE=re.compile(r'(?<!\d)(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?(?!\d)')
MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
def clean(text): return re.sub(r'\s+',' ',text).strip()
def parse_date(text):
    match=DATE.search(text)
    if match:
        try:return datetime(*map(int,match.groups()),tzinfo=TZ).date()
        except ValueError:return None
    match=re.search(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2}),?\s+(20\d{2})\b',text,re.I)
    if match:
        try:return datetime(int(match[3]),MONTHS[match[1].lower()],int(match[2]),tzinfo=TZ).date()
        except ValueError:return None
    return None

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.link=None;self.meta={};self.title='';self.in_title=False;self.ignore=0;self.text=[];self.jsonld=[];self.ld=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta':
            key=a.get('property') or a.get('name') or a.get('itemprop')
            if key:self.meta[key.lower()]=a.get('content','')
        if tag=='time' and 'datetime' in a:self.meta.setdefault('time',a['datetime'])
        if tag in ('script','style'):self.ignore+=1
        if tag=='script' and a.get('type')=='application/ld+json':self.ld=''
        if tag=='title':self.in_title=True
        if tag=='a':self.link={'url':a.get('href',''),'text':''}
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
        if tag=='script' and self.ld is not None:
            try:self.jsonld.append(json.loads(self.ld))
            except ValueError:pass
            self.ld=None
        if tag=='a' and self.link is not None:
            self.links.append(self.link);self.link=None
    def handle_data(self,text):
        if self.ld is not None:self.ld+=text
        if self.in_title:self.title+=text
        if not self.ignore and text.strip():
            self.text.append(text.strip())
            if self.link is not None:self.link['text']+=text+' '

def fetch(url,allowed_hosts):
    if urlparse(url).scheme!='https' or urlparse(url).hostname not in allowed_hosts:raise ValueError('Source URL outside allowed hosts')
    request=Request(url,headers={'User-Agent':'EmbodiedMarketingCalendar/1.0 (public news collection)','Accept':'text/html,application/xhtml+xml'})
    with urlopen(request,timeout=25) as response:
        if urlparse(response.url).scheme!='https' or urlparse(response.url).hostname not in allowed_hosts:raise ValueError('Unexpected redirect destination')
        raw=response.read(3_000_000).decode('utf-8','replace')
        page=Page();page.feed(raw);return page,response.url

def published(page):
    # Ignore dateModified, copyright years and dates of unrelated stories.
    for key in ('article:published_time','og:published_time','datepublished','date','pubdate'):
        if key in page.meta:
            d=parse_date(page.meta[key])
            if d:return d
    def ld_date(item):
        if isinstance(item,dict):
            kind=item.get('@type',[])
            if isinstance(kind,str):kind=[kind]
            if any(k in ('Article','NewsArticle','BlogPosting') for k in kind):
                d=parse_date(item.get('datePublished',''))
                if d:return d
            if '@graph' in item:
                d=ld_date(item['@graph'])
                if d:return d
        elif isinstance(item,list):
            for child in item:
                d=ld_date(child)
                if d:return d
        return None
    for item in page.jsonld:
        d=ld_date(item)
        if d:return d
    # A visible time tag is used only after explicit publication metadata.
    return parse_date(page.meta.get('time',''))

def category(title):
    t=title.lower()
    brand=('春晚','演唱会','走秀','时装周','格斗','运动会','赛事','大赛','联名','快闪','表演','展会','世博','演出','开源','gala','world cup','concert','fashion','competition','medal','open-source','open source','ces','waic','wrc','mwc')
    product=('发布','新品','预订','预售','交付','量产','下线','实测','测试','试验','试点','预览','launch','unveil','preview','trial','delivers','product','production','rolled off','robotics metaplant','introduces')
    if any(word in t for word in ('白皮书','white paper','appoints','任命','首席执行官')):return 'pr'
    if any(word in t for word in brand):return 'brand'
    if any(word in t for word in product):return 'product'
    return 'pr'

def headline(text):
    s=DATE.sub('',text)
    s=re.sub(r'\b(Media Coverage|Read More|More\+|Press Release|Product News)\b','',s,flags=re.I)
    s=s.replace('查看详情','').replace('更多详情','').replace('了解更多','')
    s=re.sub(r'\s*\|\s*(Boston Dynamics|AGIBOT).*$', '',s,flags=re.I)
    return clean(s)

def collect_fourier(source,start,end):
    report={'company':source['company'],'state':'成功','count':0,'dated':0,'skipped_future':0,'no_date':0,'error':None}
    records=[]
    try:
        request=Request(source['api_url'],headers={'User-Agent':'EmbodiedMarketingCalendar/1.0','Accept':'application/json','Accept-Language':'zh_cn'})
        with urlopen(request,timeout=25) as response:
            if urlparse(response.url).hostname not in source['allowed_hosts']:raise ValueError('Unexpected API redirect')
            payload=json.loads(response.read(3_000_000))
        if payload.get('success') is not True:raise ValueError('Official news API reported failure')
        rows=payload.get('data',{}).get('content')
        if not isinstance(rows,list):raise ValueError('News API schema changed')
        if not rows:report['state']='成功（官网接口当前返回 0 条）'
        for row in rows:
            title=clean(row.get('title',''))
            day=parse_date(row.get('publishDate') or row.get('createTime') or '')
            if not title or not day:
                report['no_date']+=1;continue
            report['dated']+=1
            if day>end:report['skipped_future']+=1;continue
            if day<start:continue
            article_id=str(row.get('id',''))
            if not re.fullmatch(r'\d+',article_id):continue
            # The official list is authoritative for the headline and displayed date.
            # External links are not fetched; retain the official list as the source.
            original_link=row.get('profile','') if row.get('contentType')==2 else ''
            url=original_link if urlparse(original_link).scheme=='https' else f'https://www.fftai.com/fourier/article/{article_id}'
            notes='官网公开新闻接口采集并自动归类，事实与归类待核实。日期为官网列表展示日期，不等同于事件发生日。公司数据和领先性表述为公司口径。'
            if not row.get('publishDate'):notes+='官网未设 publishDate，采用其页面展示的 createTime 日期。'
            event={'id':'official-'+hashlib.sha256(('fourier:'+article_id).encode()).hexdigest()[:12],'company':'fourier','category':category(title),'title':title,'summary':'','year':day.year,'month':day.month,'date':day.isoformat(),'date_basis':'publication','status':'collected','sources':[{'url':url,'title':title,'publisher':source['publisher'],'published_at':day.isoformat(),'kind':'listing'},{'url':source['url'],'title':'官网新闻列表','publisher':source['publisher'],'published_at':None,'kind':'listing'}],'origin':'official','continuous':False,'added_at':end.isoformat(),'notes':notes}
            records.append(event)
        report['count']=len(records)
        if rows and report['dated']==0:report.update({'state':'日期解析需维护','error':'接口返回新闻，但没有可解析日期'})
    except Exception as exc:report.update({'state':'入口需维护','error':type(exc).__name__+': '+str(exc)[:100]})
    return records,report

def collect(source,start,end):
    if source.get('adapter')=='fourier_api':return collect_fourier(source,start,end)
    reports={'company':source['company'],'state':'成功','count':0,'dated':0,'skipped_future':0,'no_date':0,'error':None}
    candidates=[];seen=set();errors=[]
    for listing_url in [source['url'],source.get('fallback')]:
        if not listing_url:continue
        try:
            page,base=fetch(listing_url,source['allowed_hosts'])
            for link in page.links:
                href=urldefrag(urljoin(base,link['url']))[0]
                if urlparse(href).hostname not in source['allowed_hosts'] or not re.search(source['article_pattern'],href):continue
                if href in seen:continue
                text=clean(link['text']);title=headline(text)
                if not title or title.lower() in ('read more','more','more+','了解更多','查看详情'):continue
                if len(title)<8:continue
                seen.add(href);candidates.append((href,title,parse_date(text),base))
        except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:100])
        if len(candidates)>=8:break
    results=[]
    def process(candidate):
        url,title,day,listing=candidate
        notes='官网标题自动采集并归类，事实与归类仍待核实。官网发布日期不等同于事件发生日期；数据、订单和领先性表述为公司口径。'
        src={'url':url,'title':title,'publisher':source['publisher'],'published_at':day.isoformat() if day else None,'kind':'listing'}
        if not day:
            try:
                p,_=fetch(url,source['allowed_hosts']);day=published(p)
                src.update({'kind':'article','published_at':day.isoformat() if day else None})
                title=headline(p.meta.get('og:title') or title)
            except Exception:return None,'no_date'
        if not day:return None,'no_date'
        if day>end:return None,'future'
        if day<start:return None,'old'
        sources=[src]
        if src['kind']=='listing':sources.append({'url':listing,'title':'官网新闻列表（含发布日期）','publisher':source['publisher'],'published_at':None,'kind':'listing'})
        event={'id':'official-'+hashlib.sha256(url.encode()).hexdigest()[:12],'company':source['company'],'category':category(title),'title':title,'summary':'','year':day.year,'month':day.month,'date':day.isoformat(),'date_basis':'publication','status':'collected','sources':sources,'origin':'official','continuous':False,'added_at':end.isoformat(),'notes':notes}
        return event,'dated'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for event,state in pool.map(process,candidates[:40]):
            if state in ('dated','old','future'):reports['dated']+=1
            if state=='no_date':reports['no_date']+=1
            if state=='future':reports['skipped_future']+=1
            if event:results.append(event)
    reports['count']=len(results)
    if not candidates:
        reports.update({'state':'入口需维护','error':'；'.join(errors) or '页面无可解析的新闻链接（可能需要动态接口）'})
    elif candidates and reports['dated']==0:
        reports.update({'state':'日期解析需维护','error':'新闻链接可读取，但没有可靠发布日期'})
    elif not results:
        reports['state']='成功（窗口内无新增）'
    if errors and results:reports['state']='备用入口成功'
    return results,reports

def atomic_json(path,obj):
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');temp=f.name
    os.replace(temp,path)

def main():
    args=argparse.ArgumentParser();args.add_argument('--today',help='YYYY-MM-DD, for a reproducible collection');args.add_argument('--lookback-days',type=int);args.add_argument('--cloud',action='store_true',help='Mark a configured cloud schedule');opt=args.parse_args()
    now=datetime.now(TZ);end=datetime.fromisoformat(opt.today).date() if opt.today else now.date()
    data=json.loads((ROOT/'data.json').read_text());sources=json.loads((ROOT/'sources.json').read_text())
    # Look back through the last complete month, with overlap for delayed posts.
    start=(end.replace(day=1)-timedelta(days=1)).replace(day=1)-timedelta(days=7)
    if opt.lookback_days is not None:start=end-timedelta(days=opt.lookback_days)
    elif data.get('last_success_at'):start=min(start,datetime.fromisoformat(data['last_success_at']).date()-timedelta(days=7))
    existing={e['id'] for e in data['events']};added=0;health=[]
    with ThreadPoolExecutor(max_workers=7) as pool:
        for records,report in pool.map(lambda s:collect(s,start,end),sources):
            health.append(report)
            for record in records:
                if record['id'] in existing:continue
                data['events'].append(record);existing.add(record['id']);added+=1
    ok=sum(s['state'].startswith(('成功','备用')) for s in health)
    stamp=now.isoformat(timespec='seconds')
    run={'at':stamp,'window':f'{start} 至 {end}','added':added,'status':'完成' if ok==len(sources) else ('部分来源需维护' if ok else '采集失败'),'ok_sources':ok,'total_sources':len(sources),'sources':health}
    data['runs']=[run]+data.get('runs',[])[:23];data['last_collection_at']=stamp
    if ok==len(sources):data['last_success_at']=stamp
    if added:data['updated_at']=stamp
    if opt.cloud:data['automation']={'enabled':True,'cadence':'每月 1 日 10:00','timezone':'Asia/Shanghai','state':'云端月度更新已启用'}
    atomic_json(ROOT/'data.json',data);build()
    print(json.dumps(run,ensure_ascii=False,indent=2))
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
