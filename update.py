import json, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

POS=["surge","soar","rally","record high","all-time high","beat estimates","upgrade","bullish","optimism","inflow","rebound","강세","급등","상승","신고가","사상 최고","호실적","상향","낙관","반등","순매수","매수세","성장","호재"]
NEG=["crash","plunge","selloff","sell-off","panic","recession","downgrade","miss estimates","bearish","outflow","volatility spike","war","default","폭락","급락","하락","투매","패닉","침체","경기 둔화","하향","악재","공포","순매도","매도세","위기","부진","손실"]
KST=timezone(timedelta(hours=9))
def sentiment(text):
    t=text.lower()
    p=sum(1 for w in POS if w.lower() in t)
    n=sum(1 for w in NEG if w.lower() in t)
    return p,n,("긍정" if p>n else "부정" if n>p else "중립")
def calc(items):
    p=n=0
    for x in items:
        a,b,_=sentiment(x.get("title","")+" "+x.get("summary",""));p+=a;n+=b
    return (round(50+50*(p-n)/max(p+n,1)) if p+n else 50),p,n
def get_rss(query,hl,gl,ceid,source):
    url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":query,"hl":hl,"gl":gl,"ceid":ceid})
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    try: root=ET.fromstring(urllib.request.urlopen(req,timeout=25).read())
    except Exception as e: print("RSS error",source,e);return []
    out=[]
    for it in root.findall(".//item")[:40]:
        title=it.findtext("title","");link=it.findtext("link","")
        desc=re.sub("<[^>]+>"," ",it.findtext("description",""))
        src=it.find("source");publisher=src.text if src is not None else source
        try: dt=parsedate_to_datetime(it.findtext("pubDate","")).astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except: dt=""
        p,n,label=sentiment(title+" "+desc)
        out.append({"title":title,"link":link,"summary":desc[:220],"source":publisher,"date":dt,"sentiment":label})
    return out
def unique(xs):
    seen=set();out=[]
    for x in xs:
        k=re.sub(r"[^a-z0-9가-힣]","",x["title"].lower())
        if k and k not in seen:seen.add(k);out.append(x)
    return out
def result(name,flag,items):
    s,p,n=calc(items);return {"name":name,"flag":flag,"score":s,"count":len(items),"positive":p,"negative":n}

# 뉴스 피드: Google News 검색 RSS의 최근 1일 기사
us_news=unique(get_rss('(US stock market OR Wall Street OR S&P 500 OR Nasdaq) when:1d','en-US','US','US:en','US News'))
kr_news=unique(get_rss('(한국 증시 OR 코스피 OR 코스닥 OR 국내 주식시장) when:1d','ko-KR','KR','KR:ko','KR News'))

# 커뮤니티: Reddit 검색 RSS 및 Google News 색인 공개 페이지(디시/네이버 카페).
# 비공개/로그인 전용 카페와 색인되지 않은 글은 수집할 수 없습니다.
reddit=unique(get_rss('site:reddit.com (stocks OR investing OR wallstreetbets OR stocks korea) when:2d','en-US','US','US:en','Reddit'))
dc=unique(get_rss('(site:dcinside.com OR site:gall.dcinside.com) (주식 OR 미국주식 OR 코스피 OR 나스닥) when:2d','ko-KR','KR','KR:ko','DCInside'))
cafe=unique(get_rss('(site:cafe.naver.com) (주식 OR 미국주식 OR 코스피 OR 나스닥) when:2d','ko-KR','KR','KR:ko','Naver Cafe'))

# 국가별 커뮤니티 심리는 검색어 기반 분류. 미국/한국 게시판이 명확히 구분되지 않는 게시물은 시장별 검색어에 따라 수집.
# 미국 시장 커뮤니티: Reddit 중심 + 국내 커뮤니티의 미국주식/나스닥 검색 결과
us_comm=unique(reddit+get_rss('(site:dcinside.com OR site:gall.dcinside.com OR site:cafe.naver.com) (미국주식 OR 나스닥 OR S&P500) when:2d','ko-KR','KR','KR:ko','Korean community'))
# 한국 시장 커뮤니티: 국내 주식/코스피/코스닥 검색 결과 + Reddit 한국 주식 언급
kr_comm=unique(dc+cafe+get_rss('site:reddit.com (Korea stocks OR KOSPI OR KOSDAQ) when:2d','en-US','US','US:en','Reddit Korea stocks'))

now=datetime.now(KST)
data={
 "as_of":(now-timedelta(days=1)).strftime("%Y-%m-%d (전날 기준)"),
 "updated_at":now.strftime("%Y-%m-%d %H:%M KST"),
 "news_scores":[result("미국 증시","🇺🇸",us_news),result("한국 증시","🇰🇷",kr_news)],
 "community_scores":[result("미국 관련 커뮤니티","🇺🇸",us_comm),result("한국 관련 커뮤니티","🇰🇷",kr_comm)],
 "news":(us_news[:12]+kr_news[:12])[:24],
 "posts":(us_comm[:12]+kr_comm[:12])[:24],
 "community_sources":{"reddit":len(reddit),"dcinside":len(dc),"naver_cafe":len(cafe)}
}
with open("data.json","w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
print("Updated:",data["updated_at"],"news",len(us_news),len(kr_news),"community",len(us_comm),len(kr_comm))
