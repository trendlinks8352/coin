#!/usr/bin/env python3
"""Daily Nasdaq + semiconductor news/community sentiment collector.

News sources: Google News RSS multi-query.
Community: Google News RSS indexing of public Reddit, DCInside and Naver Cafe pages only;
no Reddit API/OAuth. No browser-side secrets. News and community scores are independent.
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
WINDOW_END = NOW
WINDOW_START = NOW - timedelta(hours=24)
DAY_KEY = NOW.strftime("%Y-%m-%d")
UA = "Mozilla/5.0 (compatible; NasdaqSemiSentiment/2.0; +https://github.com/)"
REQUEST_TIMEOUT = 20
MAX_ITEMS_PER_QUERY = 100
OUTPUT_DIR = Path("output")

US_NEWS_QUERIES = [
    '(Nasdaq OR "Nasdaq 100" OR "Nasdaq Composite" OR SOX) (semiconductor OR chip OR Nvidia OR AMD OR Micron OR Broadcom)',
    '(HBM OR DRAM OR NAND OR TSMC OR ASML OR Intel OR Qualcomm) (earnings OR demand OR supply OR stocks OR semiconductor)'
]
KR_NEWS_QUERIES = [
    '(나스닥 OR 나스닥100 OR SOX OR 필라델피아반도체지수) (미국주식 OR 반도체 OR 엔비디아 OR AMD)',
    '(삼성전자 OR SK하이닉스 OR HBM OR D램 OR 낸드 OR 마이크론) (실적 OR 수요 OR 공급 OR 주가 OR 반도체)'
]
US_COMMUNITY_QUERIES = [
    'site:reddit.com (Nasdaq OR semiconductor OR Nvidia OR AMD OR Micron OR SOXL)',
    'site:reddit.com (HBM OR DRAM OR NAND OR TSMC OR Broadcom OR chip stocks)'
]
KR_COMMUNITY_QUERIES = [
    '(site:dcinside.com OR site:gall.dcinside.com OR site:cafe.naver.com) (삼성전자 OR SK하이닉스 OR HBM OR D램 OR 낸드 OR 반도체)',
    'site:reddit.com (Samsung Electronics OR SK Hynix OR Korean semiconductor OR HBM)'
]

POS = [
    "beat estimates", "beats estimates", "topped estimates", "earnings beat", "revenue beat",
    "raises guidance", "raised guidance", "guidance raised", "raises full-year outlook",
    "record revenue", "record profits", "record earnings", "strong earnings", "earnings growth",
    "higher than expected", "better than expected", "above expectations", "profit margin expansion",
    "margin expansion", "positive earnings surprise", "upside surprise", "accelerating growth",
    "strong free cash flow", "cash flow improvement", "strong demand", "robust demand",
    "demand recovery", "demand rebound", "demand acceleration", "orders increase", "order growth",
    "rising orders", "book-to-bill improvement", "pricing power", "price increase",
    "higher chip prices", "memory price recovery", "tight supply", "supply shortage",
    "capacity sold out", "high utilization", "inventory normalization", "inventory decline",
    "channel inventory decline", "ai demand boom", "ai spending increase", "ai infrastructure spending",
    "hyperscaler capex increase", "data center demand", "accelerating hbm demand", "hbm adoption",
    "advanced packaging demand", "leading-edge demand", "yield improvement", "higher wafer output",
    "production ramp", "capacity expansion", "mass production begins", "technology breakthrough",
    "market share gains", "design win", "large customer order", "long-term supply agreement",
    "new product launch", "technology leadership", "upgrade", "upgraded to buy", "outperform",
    "overweight rating", "buy rating", "price target raised", "price target increase", "bullish",
    "breakout", "rally", "surge", "soar", "rebound", "recovery", "inflows", "strong buying",
    "short covering rally", "shares gain", "stock rises", "stock jumps", "higher highs",
    "new 52-week high", "all-time high", "positive momentum",
    "호실적", "어닝 서프라이즈", "실적 개선", "실적 상회", "시장 예상 상회",
    "컨센서스 상회", "매출 증가", "매출 성장", "영업이익 증가", "영업이익 개선",
    "순이익 증가", "이익률 개선", "마진 개선", "가이던스 상향", "실적 전망 상향",
    "연간 전망 상향", "수익성 개선", "흑자 전환", "적자 축소", "강한 수요",
    "수요 증가", "수요 회복", "수요 확대", "주문 증가", "수주 증가", "수주 확대",
    "공급 부족", "공급 타이트", "가격 상승", "메모리 가격 반등", "메모리 가격 상승",
    "재고 감소", "재고 정상화", "가동률 상승", "생산량 증가", "수율 개선",
    "양산 돌입", "양산 확대", "증설", "생산능력 확대", "설비투자 확대", "고객사 확대",
    "점유율 상승", "시장점유율 확대", "기술 경쟁력 강화", "기술 우위", "신제품 출시",
    "대규모 수주", "장기 공급 계약", "수혜 기대", "목표가 상향", "목표주가 상향",
    "투자의견 상향", "매수 의견", "비중 확대", "강력 매수", "상승", "급등", "반등",
    "회복", "신고가", "사상 최고가", "매수세", "순매수", "외국인 순매수",
    "기관 순매수", "주가 상승", "강세", "긍정적 전망", "성장 기대", "호재",
    "투자 확대", "긍정"
]

NEG = [
    "miss estimates", "missed estimates", "earnings miss", "revenue miss",
    "cuts guidance", "cut guidance", "guidance cut", "lowers guidance",
    "lowers full-year outlook", "weak earnings", "earnings decline", "revenue decline",
    "profit decline", "lower than expected", "below expectations",
    "negative earnings surprise", "downside surprise", "margin contraction",
    "profit warning", "loss widens", "cash flow deterioration", "weak demand",
    "soft demand", "demand slowdown", "demand weakness", "demand deterioration",
    "orders decline", "order cancellations", "pricing pressure", "price cuts",
    "falling chip prices", "memory price decline", "oversupply", "excess supply",
    "supply glut", "inventory buildup", "rising inventory", "inventory glut",
    "capacity glut", "low utilization", "underutilization", "production cuts",
    "capacity reduction", "delayed production", "ai spending slowdown", "capex cuts",
    "hyperscaler capex slowdown", "slower data center spending", "hbm shortage delays",
    "yield problems", "yield deterioration", "manufacturing defect", "production disruption",
    "export restrictions", "export ban", "sanctions", "geopolitical risk", "customer loss",
    "market share loss", "design loss", "order delay", "product delay", "recall",
    "technology setback", "competition intensifies", "downgrade", "downgraded to sell",
    "underperform", "underweight rating", "sell rating", "price target cut",
    "price target lowered", "bearish", "selloff", "sell-off", "plunge", "plunges",
    "crash", "slump", "tumble", "shares fall", "stock drops", "stock falls",
    "sharp decline", "risk-off", "outflows", "heavy selling", "selling pressure",
    "breakdown", "lower lows", "negative momentum", "52-week low",
    "실적 부진", "어닝 쇼크", "실적 하회", "시장 예상 하회", "컨센서스 하회",
    "매출 감소", "매출 둔화", "영업이익 감소", "영업이익 악화", "순이익 감소",
    "이익률 하락", "마진 악화", "가이던스 하향", "실적 전망 하향",
    "연간 전망 하향", "수익성 악화", "적자 전환", "적자 확대", "수요 둔화",
    "수요 감소", "수요 부진", "수요 위축", "주문 감소", "수주 감소", "주문 취소",
    "공급 과잉", "재고 증가", "재고 부담", "재고 급증", "가격 하락",
    "메모리 가격 하락", "가동률 하락", "생산 차질", "생산 중단", "수율 악화",
    "양산 지연", "증설 지연", "투자 축소", "설비투자 감소", "고객사 이탈",
    "점유율 하락", "시장점유율 하락", "경쟁 심화", "기술 격차 축소",
    "수출 규제", "수출 제한", "제재", "관세 부담",
    "목표가 하향", "목표주가 하향", "투자의견 하향", "매도 의견", "비중 축소",
    "하락", "급락", "폭락", "약세", "매도세", "순매도", "외국인 순매도",
    "기관 순매도", "주가 하락", "부정적 전망", "악재", "성장 둔화"
]

def clean_text(value):
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST)
    except (TypeError, ValueError, OverflowError):
        return None

def google_news_url(query):
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)

def fetch_rss(query):
    request = urllib.request.Request(
        google_news_url(query),
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml"}
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
        root = ET.fromstring(payload)
    except Exception as exc:
        print(f"[WARN] RSS fetch failed: {query[:70]}... ({exc})")
        return []

    items = []
    for node in root.findall(".//item")[:MAX_ITEMS_PER_QUERY]:
        title = clean_text(node.findtext("title"))
        link = (node.findtext("link") or "").strip()
        description = clean_text(node.findtext("description"))
        pub_date = parse_date(node.findtext("pubDate"))
        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None else "")
        if not title:
            continue
        if pub_date and not (WINDOW_START <= pub_date <= WINDOW_END):
            continue
        items.append({
            "title": title,
            "description": description,
            "url": link,
            "source": source,
            "published_at": pub_date.isoformat() if pub_date else "",
            "published_dt": pub_date,
            "query": query,
        })
    return items

def collect_queries(queries, category, region):
    collected = []
    for query in queries:
        print(f"[INFO] Searching {category}/{region}: {query[:90]}")
        for item in fetch_rss(query):
            item["category"] = category
            item["region"] = region
            collected.append(item)
        time.sleep(0.4)
    # Deduplicate by URL, falling back to title.
    unique = {}
    for item in collected:
        key = item["url"] or item["title"].lower()
        if key not in unique:
            unique[key] = item
    return list(unique.values())

def score_text(text):
    normalized = (text or "").lower()
    pos_hits = [term for term in POS if term.lower() in normalized]
    neg_hits = [term for term in NEG if term.lower() in normalized]
    # One article contributes one bounded score; phrase counts are retained for audit.
    raw = len(pos_hits) - len(neg_hits)
    score = 0 if raw == 0 else (1 if raw > 0 else -1)
    return score, pos_hits, neg_hits

def enrich(items):
    for item in items:
        text = f"{item['title']} {item['description']}"
        score, pos_hits, neg_hits = score_text(text)
        item["sentiment_score"] = score
        item["positive_hits"] = pos_hits
        item["negative_hits"] = neg_hits
        item.pop("published_dt", None)
    return items

def summarize(items):
    total = len(items)
    positive = sum(x["sentiment_score"] > 0 for x in items)
    negative = sum(x["sentiment_score"] < 0 for x in items)
    neutral = total - positive - negative
    net = (positive - negative) / total if total else 0.0
    return {
        "articles": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "net_sentiment": round(net, 4),
        "positive_ratio": round(positive / total, 4) if total else 0.0,
        "negative_ratio": round(negative / total, 4) if total else 0.0,
    }

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    news = []
    news += collect_queries(US_NEWS_QUERIES, "news", "US")
    news += collect_queries(KR_NEWS_QUERIES, "news", "KR")

    community = []
    community += collect_queries(US_COMMUNITY_QUERIES, "community", "US")
    community += collect_queries(KR_COMMUNITY_QUERIES, "community", "KR")

    news = enrich(news)
    community = enrich(community)

    result = {
        "date": DAY_KEY,
        "timezone": "Asia/Seoul",
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "method": "Google News RSS keyword sentiment; news and community scored independently",
        "news_summary": summarize(news),
        "community_summary": summarize(community),
        "news": news,
        "community": community,
    }

    json_path = OUTPUT_DIR / f"nasdaq_semiconductor_sentiment_{DAY_KEY}.json"
    csv_path = OUTPUT_DIR / f"nasdaq_semiconductor_sentiment_{DAY_KEY}.csv"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    csv_fields = [
        "category", "region", "published_at", "source", "title", "description",
        "sentiment_score", "positive_hits", "negative_hits", "url"
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for item in news + community:
            row = dict(item)
            row["positive_hits"] = "; ".join(row.get("positive_hits", []))
            row["negative_hits"] = "; ".join(row.get("negative_hits", []))
            writer.writerow(row)

    print("\n=== 24-hour sentiment summary ===")
    print("News     :", json.dumps(result["news_summary"], ensure_ascii=False))
    print("Community:", json.dumps(result["community_summary"], ensure_ascii=False))
    print(f"\n[OK] JSON saved: {json_path}")
    print(f"[OK] CSV saved : {csv_path}")

if __name__ == "__main__":
    main()
