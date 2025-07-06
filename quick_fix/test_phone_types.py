"""
새로운 PDF로 전화번호 종류별 파싱 테스트
"""
import sys
import os

# 메인 디렉토리를 패스에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import process_pdf

def test_phone_type_classification():
    """새로운 PDF로 전화번호 종류별 분류 테스트"""
    
    # 업로드된 새 PDF 파일이 있는지 확인
    pdf_files = []
    base_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation"
    
    # PDF 파일들 찾기
    for file in os.listdir(base_path):
        if file.endswith('.pdf'):
            pdf_files.append(os.path.join(base_path, file))
    
    if not pdf_files:
        print("PDF 파일을 찾을 수 없습니다.")
        return
    
    # 가장 최근 PDF 사용 (파일명 기준)
    latest_pdf = max(pdf_files, key=os.path.getmtime)
    print(f"테스트할 PDF: {os.path.basename(latest_pdf)}")
    
    print("\n=== 전화번호 종류별 분류 테스트 ===")
    
    invoice_data, billing_month = process_pdf(latest_pdf)
    
    if invoice_data:
        print(f"청구월: {billing_month}")
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
        
        print(f"\n=== 전화번호 종류별 통계 ===")
        total_amount = 0
        for phone_type, phones in phone_types.items():
            if phones:
                count = len(phones)
                type_total = sum(amount for phone, amount in phones)
                total_amount += type_total
                print(f"{phone_type}: {count}개, 합계 {type_total:,}원")
                
                # 샘플 몇 개 출력
                print(f"  샘플:")
                for i, (phone, amount) in enumerate(phones[:3], 1):
                    print(f"    {i}. {phone} → {amount:,}원")
                if len(phones) > 3:
                    print(f"    ... 외 {len(phones) - 3}개 더")
                print()
        
        print(f"전체 합계: {total_amount:,}원")
    
    else:
        print("파싱 실패!")

if __name__ == "__main__":
    test_phone_type_classification()
