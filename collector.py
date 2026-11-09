#!/usr/bin/env python3
"""Daily Nasdaq + semiconductor news/community sentiment collector.
News sources: Google News RSS multi-query.
Community: Reddit official OAuth API (optional) + publicly indexed DCInside/Naver Cafe Google News RSS.
No browser-side secrets. Scores are independent: news != community.
"""
import os, json, re, math, time, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
DAY_START = datetime(NOW.year, NOW.month, NOW.day, tzinfo=KST) - timedelta(days=1)
DAY_END = DAY_START + timedelta(days=1)
UA = "Mozilla/5.0 (compatible; NasdaqSemiSentiment/2.0; +https://github.com/)"

# Search scope is deliberately limited to Nasdaq and semiconductor themes.
US_NEWS_QUERIES = [
    'Nasdaq Composite OR Nasdaq 100 OR Nasdaq stocks',
    'Philadelphia Semiconductor Index OR SOX index OR semiconductor stocks',
    'Nvidia OR AMD OR Broadcom semiconductor earnings',
    'Micron OR memory chip OR HBM OR DRAM OR NAND',
    'TSMC OR ASML OR Intel OR Qualcomm semiconductor',
    'AI chip demand OR semiconductor supply chain'
]
KR_NEWS_QUERIES = [
    '나스닥 OR 나스닥100 OR 나스닥종합지수',
    '미국 반도체주 OR 필라델피아 반도체지수 OR SOX',
    '삼성전자 OR SK하이닉스 반도체 실적',
    'HBM OR D램 OR 낸드 OR 메모리 반도체',
    '한미반도체 OR 반도체 장비 OR 반도체 소재',
    '엔비디아 OR AMD OR 마이크론 반도체'
]
US_COMMUNITY_QUERIES = [
    'site:reddit.com/r/stocks (Nasdaq OR semiconductor OR Nvidia OR AMD OR Micron)',
    'site:reddit.com/r/investing (Nasdaq OR semiconductor OR chip stocks)',
    'site:reddit.com/r/semiconductor (chip OR semiconductor OR HBM)',
    'site:reddit.com/r/NVDA_Stock Nvidia semiconductor',
    'site:reddit.com/r/AMD_Stock AMD semiconductor',
    'site:reddit.com/r/wallstreetbets (Nasdaq OR NVDA OR AMD OR SOXL OR semiconductor)',
    '(site:dcinside.com OR site:gall.dcinside.com) (나스닥 OR 미국반도체 OR 엔비디아 OR 마이크론 OR SOXL)',
    'site:cafe.naver.com (나스닥 OR 미국반도체 OR 엔비디아 OR 마이크론)'
]
KR_COMMUNITY_QUERIES = [
    '(site:dcinside.com OR site:gall.dcinside.com) (삼성전자 OR SK하이닉스 OR HBM OR D램 OR 낸드 OR 반도체)',
    'site:cafe.naver.com (삼성전자 OR SK하이닉스 OR HBM OR D램 OR 낸드 OR 반도체)',
    'site:reddit.com (Samsung Electronics OR SK Hynix OR KOSPI semiconductor OR Korean semiconductor)'
]

POS = [
    "beat estimates","raises guidance","guidance raised","record revenue","strong demand",
    "upgrade","outperform","buy rating","price target raised","bullish","breakout","rally",
    "surge","soar","rebound","inflows","strong earnings","higher than expected",
    "호실적","어닝 서프라이즈","실적 개선","실적 상회","목표가 상향","투자의견 상향",
    "강한 수요","수요 증가","공급 부족","상승","급등","반등","신고가","매수세","순매수",
    "수혜","성장","흑자 전환","증설","투자 확대","긍정"
]
NEG = [
    "miss estimates","cuts guidance","guidance cut","weak demand","downgrade","underperform",
    "sell rating","price target cut","bearish","selloff","sell-off","plunge","crash",
    "shortage eases","oversupply","inventory buildup","export ban","sanctions","delay",
    "실적 부진","어닝 쇼크","실적 하회","목표가 하향","투자의견 하향","수요 둔화",
    "공급 과잉","재고 증가","가격 하락","하락","급락","폭락","매도세","순매도","악재",
    "규제","수출 제한","제재","투자 축소","감산","지연","적자","우려","경고","침체"
]
# A neutral mention of a company/index is not itself positive or negative.
NEGATIONS = ["not ", "no ", "isn't ", "wasn't ", "아니다", "않다", "없다", "못", "아직"]
TOPIC = re.compile(
    r"\b(nasdaq|nasdaq.?100|nasdaq composite|sox|philadelphia semiconductor|"
    r"semiconductor|semis|chip|nvidia|nvda|amd|broadcom|avgo|micron|mu|tsmc|"
    r"asml|intel|qualcomm|smh|soxl|hbm|dram|nand|memory chip)\b|"
    r"나스닥|반도체|엔비디아|삼성전자|sk하이닉스|하이닉스|마이크론|"
    r"에이엠디|브로드컴|tsmc|에이에스엠엘|hbm|디램|d램|낸드|메모리"
    , re.I
)

def clean_html(s):
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s or "")
    return re.sub(r"<[^>]+>", " ", unescape(s)).strip()

def parse_date(s):
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(KST)
    except Exception:
        return None

def in_previous_day(d):
    return bool(d and DAY_START <= d < DAY_END)

def sentiment(text):
    t = re.sub(r"\s+", " ", (text or "").lower())
    p_terms = [w for w in POS if w.lower() in t]
    n_terms = [w for w in NEG if w.lower() in t]
    # Avoid counting a phrase as positive if an explicit negation is immediately before it.
    p = sum(1 for w in p_terms if not any((neg + w.lower()) in t for neg in NEGATIONS))
    n = len(n_terms)
    # Avoid interpreting "not bad" and "not weak" as negative.
    n = sum(1 for w in n_terms if not any((neg + w.lower()) in t for neg in NEGATIONS))
    raw = p - n
    label = "긍정" if raw > 0 else "부정" if raw < 0 else "중립"
    return {"sentiment":label, "signal":1 if raw>0 else -1 if raw<0 else 0,
            "positive_hits":p, "negative_hits":n,
            "matched_positive":p_terms[:4], "matched_negative":n_terms[:4]}

def google_rss(query, hl, gl, ceid, source_type, region, query_id):
    params = urllib.parse.urlencode({"q": query + " when:3d", "hl": hl, "gl": gl, "ceid": ceid})
    url = "https://news.google.com/rss/search?" + params
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print("RSS_FAIL", query_id, str(e)[:180])
        return []
    out=[]
    for it in root.findall(".//item"):
        title=clean_html(it.findtext("title",""))
        link=it.findtext("link","")
        desc=clean_html(it.findtext("description",""))
        pub=it.findtext("pubDate","")
        dt=parse_date(pub)
        if not in_previous_day(dt): continue
        source_el=it.find("source")
        publisher=source_el.text if source_el is not None and source_el.text else source_type
        text=title+" "+desc
        if not TOPIC.search(text): continue
        s=sentiment(text)
        out.append({
            "id": hashlib_id(title+link), "title":title, "link":link, "summary":desc[:360],
            "source":publisher, "source_type":source_type, "region":region,
            "published_at":dt.isoformat(), "published_label":dt.strftime("%m-%d %H:%M"),
            **s, "query_id":query_id
        })
    return out

def hashlib_id(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8","ignore")).hexdigest()[:20]

def reddit_token():
    cid=os.getenv("REDDIT_CLIENT_ID"); secret=os.getenv("REDDIT_CLIENT_SECRET")
    if not cid or not secret: return None
    body=urllib.parse.urlencode({"grant_type":"client_credentials"}).encode()
    req=urllib.request.Request("https://www.reddit.com/api/v1/access_token",data=body,
        headers={"Authorization":"Basic "+__import__("base64").b64encode((cid+":"+secret).encode()).decode(),
                 "User-Agent":os.getenv("REDDIT_USER_AGENT","script:nasdaq-semi-sentiment:v2.0 (contact: repo owner)")})
    try:
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read()).get("access_token")
    except Exception as e:
        print("REDDIT_AUTH_FAIL",str(e)[:180]);return None

def reddit_posts(subreddits, region):
    token=reddit_token()
    if not token:
        print("REDDIT_SKIPPED: set GitHub Secrets REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")
        return []
    ua=os.getenv("REDDIT_USER_AGENT","script:nasdaq-semi-sentiment:v2.0 (contact: repo owner)")
    out=[]
    for sub in subreddits:
        url=f"https://oauth.reddit.com/r/{urllib.parse.quote(sub)}/new?limit=100"
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"User-Agent":ua})
        try:
            with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read())
        except Exception as e:
            print("REDDIT_FETCH_FAIL",sub,str(e)[:120]);continue
        for child in data.get("data",{}).get("children",[]):
            d=child.get("data",{})
            created=datetime.fromtimestamp(d.get("created_utc",0),timezone.utc).astimezone(KST)
            if not in_previous_day(created): continue
            title=d.get("title",""); body=d.get("selftext","")
            text=title+" "+body
            if not TOPIC.search(text): continue
            s=sentiment(text)
            permalink="https://www.reddit.com"+d.get("permalink","")
            out.append({"id":d.get("id") or hashlib_id(title+permalink),"title":title,
                "link":permalink,"summary":body[:500],"source":"Reddit r/"+sub,
                "source_type":"Reddit","region":region,"published_at":created.isoformat(),
                "published_label":created.strftime("%m-%d %H:%M"),"upvotes":d.get("score",0),
                "comments":d.get("num_comments",0),**s})
        time.sleep(0.35)
    return out

def dedupe(items):
    seen=set(); result=[]
    for x in sorted(items,key=lambda z:z.get("published_at",""),reverse=True):
        key=re.sub(r"[^a-z0-9가-힣]","",x.get("title","").lower())
        if key and key not in seen:
            seen.add(key);result.append(x)
    return result

def calc(items):
    if not items:
        return {"score":None,"label":"데이터 부족","count":0,"positive":0,"neutral":0,"negative":0,
                "confidence":"산출 불가","coverage":"전날 수집 결과 0건"}
    pos=sum(1 for x in items if x["signal"]==1)
    neg=sum(1 for x in items if x["signal"]==-1)
    neu=len(items)-pos-neg
    # Each distinct item gets equal weight; neutral is midpoint. Score range 0..100.
    score=round(100*(pos+0.5*neu)/len(items))
    confidence="높음" if len(items)>=40 else "보통" if len(items)>=15 else "낮음"
    label=("극심한 공포" if score<=20 else "공포" if score<=40 else
           "중립" if score<=60 else "탐욕" if score<=80 else "극심한 환희")
    return {"score":score,"label":label,"count":len(items),"positive":pos,"neutral":neu,
            "negative":neg,"confidence":confidence,
            "coverage":f"긍정 {pos}건 · 중립 {neu}건 · 부정 {neg}건"}

def collect_many(queries, hl, gl, ceid, source_type, region, prefix):
    all_items=[]
    for i,q in enumerate(queries,1):
        all_items.extend(google_rss(q,hl,gl,ceid,source_type,region,f"{prefix}-{i}"))
        time.sleep(0.15)
    return dedupe(all_items)

def main():
    us_news=collect_many(US_NEWS_QUERIES,"en-US","US","US:en","뉴스","US","us-news")
    kr_news=collect_many(KR_NEWS_QUERIES,"ko-KR","KR","KR:ko","뉴스","KR","kr-news")

    # Reddit official API is used only when OAuth credentials are configured.
    us_reddit=reddit_posts(["stocks","investing","semiconductor","NVDA_Stock","AMD_Stock","wallstreetbets"],"US")
    kr_reddit=reddit_posts(["korea","stocks","investing"],"KR")
    # Google News indexing is a fallback discovery route for public DCInside/Naver Cafe pages.
    us_public=collect_many(US_COMMUNITY_QUERIES[6:],"ko-KR","KR","KR:ko","커뮤니티","US","us-public-community")
    kr_public=collect_many(KR_COMMUNITY_QUERIES[:2],"ko-KR","KR","KR:ko","커뮤니티","KR","kr-public-community")
    # Restrict Reddit posts to relevant market-specific keywords before combining.
    us_reddit=[x for x in us_reddit if re.search(r"nasdaq|sox|nvidia|nvda|amd|micron|tsmc|asml|intel|semiconductor|chip|hbm|dram|nand|smh|soxl",x["title"]+" "+x["summary"],re.I)]
    kr_reddit=[x for x in kr_reddit if re.search(r"korea|kospi|kosdaq|samsung|sk hynix|semiconductor|hbm|dram|nand|삼성|하이닉스|반도체",x["title"]+" "+x["summary"],re.I)]

    us_comm=dedupe(us_reddit+us_public)
    kr_comm=dedupe(kr_reddit+kr_public)
    groups={
        "us_news":us_news,"kr_news":kr_news,"us_community":us_comm,"kr_community":kr_comm
    }
    summaries={k:calc(v) for k,v in groups.items()}
    # Persist actual daily history only. Never synthesize historical points.
    hist_path="history.json"
    try:
        with open(hist_path,encoding="utf-8") as f: history=json.load(f)
    except Exception: history=[]
    day=DAY_START.strftime("%Y-%m-%d")
    history=[h for h in history if h.get("date")!=day]
    history.append({"date":day,**{k:v["score"] for k,v in summaries.items()}})
    history=history[-365:]
    with open(hist_path,"w",encoding="utf-8") as f:json.dump(history,f,ensure_ascii=False,indent=2)

    sources={
      "reddit_us":len(us_reddit),"reddit_kr":len(kr_reddit),
      "public_dc_naver_us":len(us_public),"public_dc_naver_kr":len(kr_public)
    }
    data={
      "as_of":day,"updated_at":NOW.isoformat(),
      "window":{"start":DAY_START.isoformat(),"end":DAY_END.isoformat(),"label":"전날 00:00~24:00 (한국시간)"},
      "scope":"Nasdaq / semiconductor only",
      "scores":summaries,
      "source_counts":sources,
      "items":{k:v[:120] for k,v in groups.items()},
      "history":history,
      "collection_notes":[
        "뉴스와 커뮤니티는 각각 독립 산출하며 합산하지 않습니다.",
        "Reddit는 공식 OAuth API 자격 증명이 설정된 경우에만 수집합니다.",
        "디시인사이드/네이버 카페는 공개 검색 색인 RSS 결과에 한정되며 비공개/로그인 전용 글은 포함되지 않습니다.",
        "전날 데이터가 0건이면 점수를 임의로 50점 처리하지 않고 데이터 부족으로 표시합니다."
      ]
    }
    with open("data.json","w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
    print("Collected", {k:len(v) for k,v in groups.items()})
    print("Scores",summaries)

if __name__=="__main__": main()
