"""
새로운 PDF 데이터로 전화번호 종류별 테스트
"""
import sys
import os

# 메인 디렉토리를 패스에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import parse_invoice_data, get_billing_month

def test_new_pdf_data():
    """2025-04 새로운 PDF 데이터로 테스트"""
    
    # 업로드된 PDF 데이터 시뮬레이션
    new_pdf_text = """
    서비스별 상세내역
    고객명 납부번호 청구월 대표서비스번호
    (주)기업금융센타 6499056291 2025년 04월 **99-2593
    
    **99-2593
    사용요금
    전국대표번호부가이용료 20,000 원
    사용요금 계 20,000 원
    할인 -200 원
    부가가치세(세금)* 1,980 원
    합계 21,780 원
    
    **00-1631
    사용요금
    전국대표번호부가이용료 20,000 원
    사용요금 계 20,000 원
    할인 -6,140 원
    부가가치세(세금)* 1,386 원
    합계 15,246 원
    
    02)**35-6493
    사용요금
    인터넷전화기본료 1,000 원
    사용요금 계 1,000 원
    할인 -10 원
    부가가치세(세금)* 99 원
    합계 1,089 원
    
    02)**44-6801
    사용요금 인터넷전화기본료 226 원
    사용요금 계 226 원
    할인 -7 원
    부가가치세(세금)* 21 원
    합계 240 원
    
    070)**03-2575
    사용요금
    인터넷전화기본료 700 원
    부가서비스이용료 10,000 원
    사용요금 계 10,700 원
    할인 -107 원
    부가가치세(세금)* 1,059 원
    합계 11,652 원
    
    070)**60-0502
    사용요금
    인터넷전화기본료 3,000 원
    시내통화료 74,373 원
    이동통화료 19,786 원
    인터넷전화통화료(070) 5,616 원
    정보통화료 2,044 원
    부가서비스이용료 8,387 원
    사용요금 계 113,206 원
    할인 -11,813 원
    부가가치세(세금)* 10,162 원
    합계 111,555 원
    
    080)**0-7100
    사용요금
    Biz ARS 10,000 원
    착신과금 접속료 4,000 원
    사용요금 계 14,000 원
    할인 -141 원
    부가가치세(세금)* 1,385 원
    합계 15,244 원
    """
    
    print("=== 새로운 PDF 데이터 테스트 (2025-04) ===")
    
    # 청구월 추출
    billing_month = get_billing_month(new_pdf_text)
    print(f"청구월: {billing_month}")
    
    # 데이터 파싱
    invoice_data = parse_invoice_data(new_pdf_text)
    
    if invoice_data:
        print(f"파싱된 전화번호 수: {len(invoice_data)}")
        
        # 전화번호 종류별 분류
        phone_types = {
            '전국대표번호': [],
            '070번호': [],
            '02번호': [],
            '080번호': [],
            '기타': []
        }
        
        for data in invoice_data:
            phone = data['전화번호']
            amount = data['최종합계']
            
            if phone.startswith('**'):
                phone_types['전국대표번호'].append((phone, amount))
            elif phone.startswith('070)'):
                phone_types['070번호'].append((phone, amount))
            elif phone.startswith('02)'):
                phone_types['02번호'].append((phone, amount))
            elif phone.startswith('080)'):
                phone_types['080번호'].append((phone, amount))
            else:
                phone_types['기타'].append((phone, amount))
        
        print(f"\n=== 전화번호 종류별 결과 ===")
        total_amount = 0
        for phone_type, phones in phone_types.items():
            if phones:
                count = len(phones)
                type_total = sum(amount for phone, amount in phones)
                total_amount += type_total
                print(f"\n{phone_type}: {count}개, 합계 {type_total:,}원")
                
                # 모든 번호 출력
                for i, (phone, amount) in enumerate(phones, 1):
                    print(f"  {i}. {phone} → {amount:,}원")
        
        print(f"\n전체 합계: {total_amount:,}원")
        
        # 원본 형태 확인
        print(f"\n=== 원본 형태 확인 ===")
        for data in invoice_data:
            print(f"{data['전화번호']} (원본 형태 유지됨)")
    
    else:
        print("파싱 실패!")

if __name__ == "__main__":
    test_new_pdf_data()
