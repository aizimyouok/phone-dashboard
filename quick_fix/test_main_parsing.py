"""
메인 app.py의 개선된 파싱 함수 테스트
"""
import sys
import os

# 메인 디렉토리를 패스에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import process_pdf

def test_main_parsing():
    """메인 app.py의 파싱 함수 테스트"""
    
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    print("=== 메인 app.py 파싱 함수 테스트 ===")
    
    invoice_data, billing_month = process_pdf(pdf_path)
    
    if invoice_data:
        print(f"청구월: {billing_month}")
        print(f"파싱된 전화번호 수: {len(invoice_data)}")
        
        # 패턴별 통계
        pattern_stats = {}
        total_amount = 0
        
        for data in invoice_data:
            phone = data['전화번호']
            amount = data['최종합계']
            total_amount += amount
            
            if phone.startswith('**'):
                pattern = '전국대표번호'
            elif phone.startswith('070'):
                pattern = '070번호'
            elif phone.startswith('02'):
                pattern = '02번호'
            elif phone.startswith('080'):
                pattern = '080번호'
            else:
                pattern = '기타'
            
            if pattern not in pattern_stats:
                pattern_stats[pattern] = {'count': 0, 'total': 0}
            pattern_stats[pattern]['count'] += 1
            pattern_stats[pattern]['total'] += amount
        
        print(f"\n=== 패턴별 통계 ===")
        for pattern, stats in pattern_stats.items():
            print(f"{pattern}: {stats['count']}개, 합계 {stats['total']:,}원")
        
        print(f"\n전체 합계: {total_amount:,}원")
        
        # 샘플 데이터 출력
        print(f"\n=== 샘플 데이터 (처음 10개) ===")
        for i, data in enumerate(invoice_data[:10], 1):
            print(f"{i:2d}. {data['전화번호']} → {data['최종합계']:,}원")
    
    else:
        print("파싱 실패!")

if __name__ == "__main__":
    test_main_parsing()
