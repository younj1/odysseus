import json, os, logging, httpx
from datetime import datetime, date
from aria.aria_config import get_config
from aria.vault.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"
PORTFOLIO_FILE = "data/portfolio.json"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.3, "num_predict": 2000, "think": False}}, timeout=120)
        if resp.status_code == 200: return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e: logger.error(f"LLM error: {e}")
    return ""

def _get_client():
    config = get_config()
    obs = config.get("obsidian", {})
    return ObsidianClient(base_url=obs.get("api_url","http://172.19.16.1:27123"), api_key=obs.get("api_key",""))

def _load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
    return {"holdings": [], "watchlist": [], "transactions": [], "goals": {"target_allocation": {}}}

def _save_portfolio(data):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f: json.dump(data, f, indent=2)

def _fetch_price(symbol):
    """Fetch current price from Yahoo Finance."""
    try:
        resp = httpx.get(f"{YAHOO_URL}/{symbol}", params={"interval": "1d", "range": "5d"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("previousClose", 0) or meta.get("chartPreviousClose", 0)
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0
                return {"symbol": symbol.upper(), "price": round(price, 2), "prev_close": round(prev_close, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "currency": meta.get("currency", "USD")}
    except Exception as e:
        logger.error(f"Price fetch failed for {symbol}: {e}")
    return None

def add_holding(symbol, shares, cost_basis):
    """Add a holding to the portfolio."""
    portfolio = _load_portfolio()
    existing = next((h for h in portfolio["holdings"] if h["symbol"] == symbol.upper()), None)
    if existing:
        total_shares = existing["shares"] + shares
        total_cost = (existing["shares"] * existing["cost_basis"]) + (shares * cost_basis)
        existing["shares"] = total_shares
        existing["cost_basis"] = round(total_cost / total_shares, 2)
    else:
        portfolio["holdings"].append({"symbol": symbol.upper(), "shares": shares, "cost_basis": cost_basis, "added": date.today().isoformat()})
    portfolio["transactions"].append({"date": date.today().isoformat(), "type": "buy", "symbol": symbol.upper(), "shares": shares, "price": cost_basis})
    _save_portfolio(portfolio)
    return True

def remove_holding(symbol, shares=None):
    """Remove or reduce a holding."""
    portfolio = _load_portfolio()
    holding = next((h for h in portfolio["holdings"] if h["symbol"] == symbol.upper()), None)
    if not holding: return False
    if shares and shares < holding["shares"]:
        holding["shares"] -= shares
    else:
        portfolio["holdings"].remove(holding)
    portfolio["transactions"].append({"date": date.today().isoformat(), "type": "sell", "symbol": symbol.upper(), "shares": shares or holding.get("shares", 0)})
    _save_portfolio(portfolio)
    return True

def add_to_watchlist(symbol):
    """Add a symbol to the watchlist."""
    portfolio = _load_portfolio()
    sym = symbol.upper()
    if sym not in portfolio["watchlist"]:
        portfolio["watchlist"].append(sym)
        _save_portfolio(portfolio)
    return True

def get_portfolio_summary():
    """Get portfolio with live prices."""
    portfolio = _load_portfolio()
    total_value = 0
    total_cost = 0
    holdings_data = []
    for h in portfolio["holdings"]:
        price_data = _fetch_price(h["symbol"])
        current_price = price_data["price"] if price_data else 0
        value = current_price * h["shares"]
        cost = h["cost_basis"] * h["shares"]
        gain = value - cost
        gain_pct = (gain / cost * 100) if cost > 0 else 0
        total_value += value
        total_cost += cost
        holdings_data.append({
            "symbol": h["symbol"], "shares": h["shares"],
            "cost_basis": h["cost_basis"], "current_price": current_price,
            "value": round(value, 2), "gain": round(gain, 2), "gain_pct": round(gain_pct, 2),
            "day_change": price_data["change"] if price_data else 0,
            "day_change_pct": price_data["change_pct"] if price_data else 0,
        })
    total_gain = total_value - total_cost
    total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0
    return {
        "holdings": holdings_data,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round(total_gain_pct, 2),
        "watchlist": portfolio.get("watchlist", []),
    }

def get_watchlist_prices():
    """Get prices for watchlist symbols."""
    portfolio = _load_portfolio()
    results = []
    for sym in portfolio.get("watchlist", []):
        data = _fetch_price(sym)
        if data: results.append(data)
    return results

def analyze_portfolio():
    """Use ARIA to analyze the portfolio."""
    summary = get_portfolio_summary()
    client = _get_client()
    vault_context = ""
    for note in ["Knowledge/Investing.md", "Knowledge/Etf.md"]:
        content = client.get_note(note)
        if content: vault_context += f"\n{content[:500]}"
    prompt = f"""Analyze this investment portfolio and provide actionable insights.

PORTFOLIO:
{json.dumps(summary['holdings'], indent=2)}

Total Value: ${summary['total_value']:,.2f}
Total Gain/Loss: ${summary['total_gain']:,.2f} ({summary['total_gain_pct']:.1f}%)

OWNER'S INVESTMENT NOTES:
{vault_context[:800]}

Provide:
1. Portfolio health assessment
2. Diversification analysis
3. Risk concerns
4. Rebalancing suggestions
5. Key metrics to watch

Note: This is informational only, not financial advice."""
    return _query_llm(prompt)

def display_portfolio():
    """Display portfolio in terminal."""
    C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
    print(f"\n{C}{B}ARIA Investment Tracker{X}")
    print(f"{D}Fetching live prices...{X}")
    summary = get_portfolio_summary()
    if not summary["holdings"]:
        print(f"\n{Y}No holdings yet. Add with: aria invest add SYMBOL SHARES COST{X}")
        return
    print(f"\n{B}Holdings{X}")
    print(f"  {'Symbol':8s} {'Shares':>8s} {'Price':>10s} {'Value':>12s} {'Gain':>12s} {'%':>8s} {'Today':>8s}")
    print(f"  {'-'*70}")
    for h in summary["holdings"]:
        gain_color = G if h["gain"] >= 0 else R
        day_color = G if h["day_change"] >= 0 else R
        print(f"  {h['symbol']:8s} {h['shares']:8.2f} ${h['current_price']:>9.2f} ${h['value']:>11,.2f} {gain_color}${h['gain']:>+11,.2f}{X} {gain_color}{h['gain_pct']:>+7.1f}%{X} {day_color}{h['day_change_pct']:>+7.2f}%{X}")
    total_color = G if summary["total_gain"] >= 0 else R
    print(f"  {'-'*70}")
    print(f"  {'TOTAL':8s} {'':8s} {'':10s} ${summary['total_value']:>11,.2f} {total_color}${summary['total_gain']:>+11,.2f}{X} {total_color}{summary['total_gain_pct']:>+7.1f}%{X}")
    # Watchlist
    watchlist = get_watchlist_prices()
    if watchlist:
        print(f"\n{B}Watchlist{X}")
        for w in watchlist:
            color = G if w["change"] >= 0 else R
            print(f"  {w['symbol']:8s} ${w['price']:>9.2f} {color}{w['change']:>+7.2f} ({w['change_pct']:>+.2f}%){X}")
