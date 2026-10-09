import unittest
from services.crawler.bank_eligibility import requires_financial_product


class BankEligibilityTests(unittest.TestCase):
    def test_financial_requirements_are_excluded(self):
        for carrier in ['KB리브모바일','KB국민은행','우리WON모바일','토스모바일']:
            for condition in ['급여이체 할인','예적금 가입 조건','금융할인','카드 실적 조건']:
                self.assertTrue(requires_financial_product(dict(telecom_name=carrier,title='요금제',raw_text=condition)))

    def test_regular_bank_plan_is_retained(self):
        self.assertFalse(requires_financial_product(dict(telecom_name='우리WON모바일',title='LTE 요금제',raw_text='금융 조건 없이 월 1만원')))

    def test_metadata_blocks_unprinted_requirement(self):
        self.assertTrue(requires_financial_product(dict(telecom_name='KB리브모바일',requires_financial_product=True)))

    def test_rule_does_not_drop_other_carriers_optional_card_ad(self):
        self.assertFalse(requires_financial_product(dict(telecom_name='아이즈모바일',raw_text='제휴 카드 실적 할인 별도')))
