"""정상가 미공개를 0원/할인가로 대체하지 않고 검증된 기간만 사용한다."""
UNKNOWN_NORMAL_MARKER='[정상가 미확인: 공식 가격 미공개/오기]'


def valid_pricing(record):
    current=record.get('discount_price');normal=record.get('normal_price');months=record.get('discount_months')
    if type(current) is not int or not 0<=current<=300000 or type(months) is not int or months < -1:
        return False
    if normal is None:
        return (months==-1 or months>0) and UNKNOWN_NORMAL_MARKER in (record.get('raw_text') or '')
    return type(normal) is int and 0<normal<=300000 and normal>=current
