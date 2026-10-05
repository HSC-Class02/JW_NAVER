"""Map DART XBRL facts conservatively and compute comparable financial ratios."""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
# Prefer XBRL tags; fall back to Korean labels only when unique within a statement.
FIELDS = {
 'revenue': ('CIS', ['Revenue', 'RevenueFromContractWithCustomer', 'SalesRevenue', '영업수익', '매출액']),
 'cost_of_sales': ('CIS', ['CostOfSales', '매출원가']),
 'gross_profit': ('CIS', ['GrossProfit', '매출총이익']),
 'operating_profit': ('CIS', ['OperatingIncomeLoss', '영업이익', '영업이익(손실)']),
 'pretax_profit': ('CIS', ['ProfitLossBeforeTax', '법인세비용차감전순이익']),
 'net_income': ('CIS', ['ProfitLoss', '당기순이익', '당기순이익(손실)']),
 'parent_income': ('CIS', ['ProfitLossAttributableToOwnersOfParent', '지배기업의 소유주에게 귀속되는 당기순이익']),
 'assets': ('BS', ['Assets', '자산총계']),
 'liabilities': ('BS', ['Liabilities', '부채총계']),
 'equity': ('BS', ['Equity', '자본총계']),
 'parent_equity': ('BS', ['EquityAttributableToOwnersOfParent', '지배기업의 소유주에게 귀속되는 자본']),
 'current_assets': ('BS', ['CurrentAssets', '유동자산']),
 'current_liabilities': ('BS', ['CurrentLiabilities', '유동부채']),
 'cash': ('BS', ['CashAndCashEquivalents', '현금및현금성자산']),
 'receivables': ('BS', ['TradeAndOtherCurrentReceivables', 'TradeReceivables', '매출채권']),
 'inventory': ('BS', ['Inventories', '재고자산']),
 'payables': ('BS', ['TradeAndOtherCurrentPayables', 'TradePayables', '매입채무']),
 'ppe': ('BS', ['PropertyPlantAndEquipment', '유형자산']),
 'cfo': ('CF', ['CashFlowsFromUsedInOperatingActivities', '영업활동현금흐름', '영업활동으로 인한 현금흐름']),
 'cfi': ('CF', ['CashFlowsFromUsedInInvestingActivities', '투자활동현금흐름']),
 'cff': ('CF', ['CashFlowsFromUsedInFinancingActivities', '재무활동현금흐름']),
 'capex_ppe': ('CF', ['PurchaseOfPropertyPlantAndEquipment', '유형자산의 취득']),
 'capex_intangible': ('CF', ['PurchaseOfIntangibleAssets', '무형자산의 취득']),
 'interest_expense': ('CIS', ['FinanceCosts', 'InterestExpense', '이자비용']),
 'tax_expense': ('CIS', ['IncomeTaxExpenseContinuingOperations', '법인세비용']),
}
# Exact standard tags for debt; no aggregate debt estimate when borrowing items unavailable.
DEBT_TAGS = ('ShorttermBorrowings', 'LongtermBorrowings', 'CurrentPortionOfLongtermBorrowings',
             'ShortTermBorrowings', 'LongTermBorrowings', 'CurrentPortionOfLongTermBorrowings')

def number(value):
    if value is None: return None
    raw = str(value).replace(',', '').strip()
    if not raw or raw in ('-', 'N/A'): return None
    try: return int(raw.replace('(', '-').replace(')', ''))
    except ValueError: return None

def ratio(n, d):
    return n / d if n is not None and d is not None and d > 0 else None

def account(row):
    return row.get('account_id', '').split(':')[-1].split('_')[-1], row.get('account_nm', '').replace(' ', '')

def field(rows, spec, amount):
    statement, names = spec
    candidates = [r for r in rows if r.get('sj_div') == statement and
                  (r.get('account_detail') in ('', '-', None) or statement != 'SCE')]
    for name in names:
        found = [r for r in candidates if name in account(r) and number(r.get(amount)) is not None]
        # Exact match only, never substring match; avoid total + component double counting.
        found = [r for r in found if name == account(r)[0] or name.replace(' ', '') == account(r)[1]]
        if len(found) == 1: return number(found[0][amount])
    return None

def extract(doc):
    f = doc['filing']; rows = doc['rows']; quarter = f['quarter']
    current = {}
    for key, spec in FIELDS.items():
        amount = 'thstrm_amount'
        if quarter != 4 and spec[0] in ('CIS', 'CF'):
            amount = 'thstrm_add_amount' if spec[0] == 'CIS' and any(r.get('thstrm_add_amount') for r in rows if r.get('sj_div') == 'CIS') else 'thstrm_amount'
        current[key] = field(rows, spec, amount)
    if current['gross_profit'] is None and current['revenue'] is not None and current['cost_of_sales'] is not None:
        current['gross_profit'] = current['revenue'] - current['cost_of_sales']
    debt = []
    for tag in DEBT_TAGS:
        matching = [r for r in rows if r.get('sj_div') == 'BS' and account(r)[0] == tag]
        if len(matching) == 1 and number(matching[0].get('thstrm_amount')) is not None:
            debt.append(number(matching[0]['thstrm_amount']))
    current['borrowings'] = sum(debt) if debt else None
    current.update({'year': f['business_year'], 'quarter': quarter, 'category': f['category'],
                    'period': f"{f['business_year']} Q{quarter}", 'basis': doc['basis'],
                    'source_url': f['url'], 'receipt_no': doc['financial_receipt_no']})
    return current

def compute(records):
    by_period = {(r['year'], r['quarter']): r for r in records}
    annual = {r['year']: r for r in records if r['quarter'] == 4}
    for r in records:
        q, y = r['quarter'], r['year']
        prev = by_period.get((y - 1, 4)) if q in (1, 4) else by_period.get((y, q - 1))
        if prev and prev['basis'] != r['basis']: prev = None
        prior_year = by_period.get((y - 1, q))
        if prior_year and prior_year['basis'] != r['basis']: prior_year = None
        def val(k): return r.get(k)
        def diff(k):
            a = val(k); b = prev.get(k) if prev else None
            return a - b if a is not None and b is not None else None
        def avg(k):
            a = val(k); b = prev.get(k) if prev else None
            return (a + b) / 2 if a is not None and b is not None else None
        # DART interim IS/CF are YTD; standalone quarter = current YTD - prior quarter YTD.
        baseline = by_period.get((y, q - 1)) if q > 1 else None
        if baseline and baseline['basis'] != r['basis']: baseline = None
        r['period_values'] = {}
        for key in ('revenue', 'cost_of_sales', 'gross_profit', 'operating_profit', 'pretax_profit', 'net_income', 'parent_income', 'cfo', 'cfi', 'cff', 'capex_ppe', 'capex_intangible'):
            a, b = val(key), baseline.get(key) if baseline else None
            # Annual column stays full year; interim shows standalone quarter where available.
            r['period_values'][key] = a if q == 1 else a - b if a is not None and b is not None else None
        v = r['period_values'] if q != 4 else r
        rev = v.get('revenue'); ni = v.get('net_income'); op = v.get('operating_profit')
        prev_revenue = prior_year.get('period_values', {}).get('revenue') if prior_year else None
        if q == 4 and prior_year: prev_revenue = prior_year.get('revenue')
        capex = [v.get('capex_ppe'), v.get('capex_intangible')]
        capex_sum = sum(abs(x) for x in capex if x is not None) if all(x is not None for x in capex) else None
        cfo = v.get('cfo')
        nd = val('borrowings') - val('cash') if val('borrowings') is not None and val('cash') is not None else None
        annual_ni = val('net_income') if q == 4 else None
        tax_rate = ratio(val('tax_expense'), val('pretax_profit')) if q == 4 else None
        invested = (avg('equity') + avg('borrowings') - avg('cash') if all(avg(k) is not None for k in ('equity','borrowings','cash')) else None)
        metrics = {
            'revenue_growth_yoy': ratio(rev, prev_revenue) - 1 if ratio(rev, prev_revenue) is not None else None,
            'gross_margin': ratio(v.get('gross_profit'), rev), 'operating_margin': ratio(op, rev),
            'net_margin': ratio(ni, rev), 'roa': ratio(annual_ni, avg('assets')),
            'roe': ratio(annual_ni, avg('equity')),
            'parent_roe': ratio(val('parent_income'), avg('parent_equity')) if q == 4 else None,
            'current_ratio': ratio(val('current_assets'), val('current_liabilities')),
            'quick_ratio': ratio(val('current_assets') - val('inventory') if val('current_assets') is not None and val('inventory') is not None else None, val('current_liabilities')),
            'debt_to_equity': ratio(val('liabilities'), val('equity')),
            'equity_ratio': ratio(val('equity'), val('assets')),
            'borrowings_to_assets': ratio(val('borrowings'), val('assets')),
            'interest_coverage': ratio(val('operating_profit'), val('interest_expense')) if q == 4 else None,
            'asset_turnover': ratio(val('revenue'), avg('assets')) if q == 4 else None,
            'dso_days': ratio(avg('receivables') * 365, val('revenue')) if q == 4 and avg('receivables') is not None else None,
            'dio_days': ratio(avg('inventory') * 365, val('cost_of_sales')) if q == 4 and avg('inventory') is not None else None,
            'cfo_to_income': ratio(cfo, ni),
            'roic': ratio(op * (1 - tax_rate), invested) if q == 4 and op is not None and tax_rate is not None and 0 <= tax_rate <= 1 else None,
        }
        r['capex'] = capex_sum; r['fcf'] = cfo - capex_sum if cfo is not None and capex_sum is not None else None
        r['net_debt'] = nd; r['metrics'] = metrics
        # Quarterly margin and growth are based on three-month flows, including Q4.
        pv = r['period_values']
        previous_quarter_year = prior_year
        previous_standalone_revenue = previous_quarter_year.get('period_values', {}).get('revenue') if previous_quarter_year else None
        quarterly_capex = None
        if pv.get('capex_ppe') is not None and pv.get('capex_intangible') is not None:
            quarterly_capex = abs(pv['capex_ppe']) + abs(pv['capex_intangible'])
        pv['capex'] = quarterly_capex
        pv['fcf'] = pv['cfo'] - quarterly_capex if pv.get('cfo') is not None and quarterly_capex is not None else None
        r['quarter_metrics'] = {
            'revenue_growth_yoy': ratio(pv.get('revenue'), previous_standalone_revenue) - 1 if ratio(pv.get('revenue'), previous_standalone_revenue) is not None else None,
            'gross_margin': ratio(pv.get('gross_profit'), pv.get('revenue')),
            'operating_margin': ratio(pv.get('operating_profit'), pv.get('revenue')),
            'net_margin': ratio(pv.get('net_income'), pv.get('revenue')),
            'cfo_to_income': ratio(pv.get('cfo'), pv.get('net_income')),
        }
        prior_half = prior_year if q == 2 else None
        r['half_metrics'] = {
            'revenue_growth_yoy': ratio(val('revenue'), prior_half.get('revenue')) - 1 if prior_half and ratio(val('revenue'), prior_half.get('revenue')) is not None else None,
            'gross_margin': ratio(val('gross_profit'), val('revenue')),
            'operating_margin': ratio(val('operating_profit'), val('revenue')),
            'net_margin': ratio(val('net_income'), val('revenue')),
            'cfo_to_income': ratio(val('cfo'), val('net_income')),
        } if q == 2 else {}
        # Market multiples, EBITDA and debt/EBITDA require reliable market/depreciation/debt components; omit until supplied.
    return records

def build_dashboard_data():
    files = sorted((ROOT / 'data/reports').glob('*.json'))
    records = [extract(json.loads(p.read_text(encoding='utf-8'))) for p in files]
    records.sort(key=lambda x: (x['year'], x['quarter']))
    filings = ROOT / 'data/filings.json'
    index = json.loads(filings.read_text(encoding='utf-8')) if filings.exists() else []
    chosen = {(x['year'], x['quarter']): x for x in records}
    for f in index:
        key = (f['business_year'], f['quarter'])
        if key not in chosen:
            chosen[key] = {'year': key[0], 'quarter': key[1], 'period': f"{key[0]} Q{key[1]}",
                           'category': f['category'], 'basis': '원문만 보관' if key[0] < 2015 else '재무 API 미제공',
                           'source_url': f['url'], 'receipt_no': f['receipt_no'], 'metrics': {}, 'period_values': {}}
    output = {'generated_at': datetime.now().astimezone().isoformat(),
              'note': '2010–2014 원문 보관, 정량 분석은 DART 구조화 API 2015년 이후 제공분만 표시',
              'records': compute(records), 'historical_only': [x for k,x in sorted(chosen.items()) if k not in {(r['year'],r['quarter']) for r in records}]}
    target = ROOT / 'docs/data.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output

if __name__ == '__main__': build_dashboard_data()
