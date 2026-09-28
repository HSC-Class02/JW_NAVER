import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analysis import compute, extract
from dart_pipeline import filing_code, filing_year

class PipelineTests(unittest.TestCase):
    def test_report_classification_and_year(self):
        self.assertEqual(filing_code('[기재정정]분기보고서 (2023.09)'), '11014')
        self.assertEqual(filing_code('반기보고서 (2010.06)'), '11012')
        self.assertEqual(filing_code('사업보고서 (2024.12)'), '11011')
        self.assertEqual(filing_year('사업보고서 (2010.12)'), 2010)
    def test_three_month_income_from_cumulative_and_annual_average_balance(self):
        def rec(year,q,revenue,assets,cfo):
            return dict(year=year,quarter=q,category='annual' if q==4 else 'quarterly',
                        revenue=revenue, gross_profit=revenue//2,operating_profit=revenue//4,
                        net_income=revenue//10,parent_income=None,cfo=cfo,cfi=None,cff=None,
                        capex_ppe=10*q,capex_intangible=5*q,assets=assets,equity=assets//2,
                        liabilities=assets//2,current_assets=100,current_liabilities=50,
                        inventory=10,cash=20,borrowings=40,receivables=None,payables=None,ppe=None,
                        cost_of_sales=None,pretax_profit=None,tax_expense=None,interest_expense=None,
                        parent_equity=None,basis='CFS',period=f'{year} Q{q}')
        result=compute([rec(2023,4,400,800,100),rec(2024,1,100,900,30),rec(2024,2,220,950,70),rec(2024,3,360,990,110),rec(2024,4,520,1000,180)])
        self.assertEqual(result[2]['period_values']['revenue'],120)
        self.assertEqual(result[4]['period_values']['revenue'],160)
        self.assertEqual(result[4]['period_values']['fcf'],55)
        self.assertAlmostEqual(result[4]['metrics']['roa'],52/900)
        self.assertAlmostEqual(result[4]['quarter_metrics']['operating_margin'],.25)
    def test_api_interim_uses_ytd_not_three_month_and_exact_tags(self):
        rows=[{'sj_div':'IS','account_id':'ifrs-full_Revenue','account_nm':'매출액','thstrm_amount':'30','thstrm_add_amount':'100'},
              {'sj_div':'IS','account_id':'ifrs-full_OperatingIncomeLoss','account_nm':'영업이익','thstrm_amount':'5','thstrm_add_amount':'12'}]
        result=extract({'filing':dict(business_year=2024,quarter=2,category='half-year',url='https://example.org'),
                        'basis':'CFS','rows':rows,'financial_receipt_no':'123'})
        self.assertEqual(result['revenue'],100)
        self.assertEqual(result['operating_profit'],12)

if __name__=='__main__':unittest.main()
