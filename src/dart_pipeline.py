"""NAVER Open DART ingest; only source-backed values reach the dashboard."""
from __future__ import annotations
import argparse
from datetime import date
import io
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CODES = {'11013': 'quarterly', '11012': 'half-year', '11014': 'quarterly', '11011': 'annual'}
QUARTER = {'11013': 1, '11012': 2, '11014': 3, '11011': 4}

class DartError(RuntimeError):
    pass

def request(path, **params):
    params['crtfc_key'] = os.environ['DART_API_KEY']
    url = 'https://opendart.fss.or.kr/api/' + path + '?' + urlencode(params)
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'JW-NAVER-financial-dashboard/1.0'}), timeout=45) as response:
                content = response.read()
            if path.endswith('.json'):
                result = json.loads(content)
                status = result.get('status')
                if status not in ('000', '013'):
                    raise DartError(f'{path}: {status} {result.get("message")}')
                return result
            if not content.startswith(b'PK'):
                raise DartError(f'{path}: ZIP response expected; got {content[:160]!r}')
            return content
        except (OSError, TimeoutError) as exc:
            if attempt == 3:
                raise DartError(f'{path}: network failed') from exc
            time.sleep(2 ** attempt)
    raise AssertionError('unreachable')

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if not path.exists() or path.read_text(encoding='utf-8') != contents:
        path.write_text(contents, encoding='utf-8')

def company_code():
    import xml.etree.ElementTree as ET
    blob = request('corpCode.xml')
    with ZipFile(io.BytesIO(blob)) as archive:
        xml = archive.read(next(n for n in archive.namelist() if n.lower().endswith('.xml')))
    root = ET.fromstring(xml)
    for item in root.findall('.//list'):
        if item.findtext('stock_code', '').strip() == '035420':
            return item.findtext('corp_code').strip()
    raise DartError('NAVER stock code 035420 not found in DART registry')

def filing_year(name):
    match = re.search(r'\((20\d{2})[./-](0?[1-9]|1[0-2])\)', name)
    return int(match.group(1)) if match else None

def filing_code(name):
    name = re.sub(r'^\[[^]]+\]\s*', '', name)
    if name.startswith('사업보고서'): return '11011'
    if name.startswith('반기보고서'): return '11012'
    if name.startswith('분기보고서'):
        match = re.search(r'\(20\d{2}[./-](\d{1,2})\)', name)
        month = int(match.group(1)) if match else 0
        return {3: '11013', 9: '11014'}.get(month)
    return None

def discover(corp, today):
    # Filing year differs from business year for annual reports (filed the next spring).
    latest = today.strftime('%Y%m%d')
    all_filings = []
    for year in range(2010, today.year + 1):
        bgn = f'{year}0101'
        end = min(f'{year}1231', latest)
        if bgn > end: continue
        page = 1
        while True:
            result = request('list.json', corp_code=corp, bgn_de=bgn, end_de=end,
                             pblntf_ty='A', page_no=page, page_count=100, last_reprt_at='N')
            if result['status'] == '013': break
            for item in result.get('list', []):
                code = filing_code(item['report_nm'])
                yr = filing_year(item['report_nm'])
                if code and yr and yr >= 2010:
                    all_filings.append({
                        'business_year': yr, 'report_code': code,
                        'category': CODES[code], 'quarter': QUARTER[code],
                        'receipt_no': item['rcept_no'], 'filed_on': item['rcept_dt'],
                        'report_name': item['report_nm'],
                        'url': 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + item['rcept_no']})
            if page >= int(result.get('total_page', 1)): break
            page += 1
    # Preserve full filing index including corrections; choose latest receipt per period.
    all_filings.sort(key=lambda x: (x['business_year'], x['quarter'], x['filed_on'], x['receipt_no']))
    dump(DATA / 'filings.json', all_filings)
    latest_by_period = {}
    for item in all_filings:
        latest_by_period[(item['business_year'], item['report_code'])] = item
    return list(latest_by_period.values())

def fetch_financials(corp, filing):
    yr, code = filing['business_year'], filing['report_code']
    for basis in ('CFS', 'OFS'):
        result = request('fnlttSinglAcntAll.json', corp_code=corp,
                         bsns_year=yr, reprt_code=code, fs_div=basis)
        if result['status'] == '000' and result.get('list'):
            rows = result['list']
            receipt = rows[0].get('rcept_no', filing['receipt_no'])
            return {'filing': filing, 'basis': basis, 'financial_receipt_no': receipt,
                    'rows': rows}
    return None

def archive_original(filing):
    target = DATA / 'archive' / (filing['receipt_no'] + '.zip')
    if target.exists(): return
    raw = request('document.xml', rcept_no=filing['receipt_no'])
    if len(raw) > 90 * 1024 * 1024:
        raise DartError('Original document exceeds safe GitHub file size; see DART filing link')
    with ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None: raise DartError('Corrupted ZIP: ' + filing['receipt_no'])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', help='YYYY-MM-DD; for testing the discovery date')
    parser.add_argument('--skip-document-archives', action='store_true', help='Save financial JSON and filing links only')
    args = parser.parse_args()
    if not os.getenv('DART_API_KEY'):
        parser.error('DART_API_KEY is required (GitHub Actions repository secret).')
    today = date.fromisoformat(args.as_of) if args.as_of else date.today()
    corp = company_code()
    selected = discover(corp, today)
    errors = []
    archive_warnings = []
    for filing in selected:
        yr, code = filing['business_year'], filing['report_code']
        target = DATA / 'reports' / f'{yr}_{code}.json'
        try:
            if not args.skip_document_archives:
                try:
                    archive_original(filing)
                except DartError as exc:
                    # The public filing link remains available even if the old ZIP is missing.
                    archive_warnings.append(f'{yr} {code}: {exc}')
            if yr >= 2015:
                # Recheck existing periods so DART corrections replace earlier snapshots.
                found = fetch_financials(corp, filing)
                if found:
                    dump(target, found)
                elif target.exists():
                    print(f'Keeping existing snapshot (API has no data): {target.name}')
                else:
                    print(f'No financial API data: {yr} {code}')
        except DartError as exc:
            errors.append(f'{yr} {code}: {exc}')
    from analysis import build_dashboard_data
    build_dashboard_data()
    dump(DATA / 'archive_status.json', {'unavailable': archive_warnings})
    if errors:
        raise DartError('Some reports could not be retrieved:\n' + '\n'.join(errors))
    print(f'Discovered {len(selected)} periods; updated data/dashboard.json')

if __name__ == '__main__':
    main()
