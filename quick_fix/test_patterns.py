"""
전화번호 패턴별 파싱 테스트 (텍스트 기반)
"""
import re

def test_phone_pattern_parsing():
    """다양한 전화번호 패턴 파싱 테스트"""
    
    # 새로운 PDF에서 추출한 샘플 텍스트
    sample_text = """
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
    
    070)**03-2575
    사용요금
    인터넷전화기본료 700 원
    부가서비스이용료 10,000 원
    사용요금 계 10,700 원
    할인 -107 원
    부가가치세(세금)* 1,059 원
    합계 11,652 원
    
    080)**0-7100
    사용요금
    Biz ARS 10,000 원
    착신과금 접속료 4,000 원
    사용요금 계 14,000 원
    할인 -141 원
    부가가치세(세금)* 1,385 원
    합계 15,244 원
    """
    
    # 전화번호 패턴들 (구체적인 패턴을 먼저 처리)
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),      # 070)**03-2575 
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),       # 02)**35-6493
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),      # 080)**0-7100
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),        # **99-2593 (가장 마지막)
    ]
    
    print("=== 전화번호 패턴별 인식 테스트 ===")
    
    lines = sample_text.split('\n')
    processed_phones = set()
    results = []
    
    for pattern, pattern_name in phone_patterns:
        print(f"\n{pattern_name} 패턴: {pattern}")
        
        for line_num, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                phone_number = match.group(0)
                
                # 중복 체크
                phone_suffix = re.sub(r'^.*\*\*', '', phone_number)
                if phone_suffix in processed_phones:
                    continue
                processed_phones.add(phone_suffix)
                
                print(f"  발견: {phone_number} (라인 {line_num})")
                
                # 합계 찾기
                search_lines = lines[line_num:line_num + 10]
                total_amount = None
                
                for i, search_line in enumerate(search_lines):
                    total_match = re.search(r'합계\s+(\d{1,3}(?:,\d{3})*)\s*원', search_line)
                    if total_match:
                        total_amount = int(total_match.group(1).replace(',', ''))
                        print(f"    → 합계: {total_amount:,}원")
                        break
                
                if total_amount:
                    results.append({
                        'type': pattern_name,
                        'phone': phone_number,
                        'amount': total_amount
                    })
    
    print(f"\n=== 파싱 결과 요약 ===")
    type_stats = {}
    for result in results:
        phone_type = result['type']
        if phone_type not in type_stats:
            type_stats[phone_type] = {'count': 0, 'total': 0}
        type_stats[phone_type]['count'] += 1
        type_stats[phone_type]['total'] += result['amount']
    
    total_sum = 0
    for phone_type, stats in type_stats.items():
        print(f"{phone_type}: {stats['count']}개, 합계 {stats['total']:,}원")
        total_sum += stats['total']
    
    print(f"\n전체 합계: {total_sum:,}원")
    
    # 각 전화번호 종류별 예시
    print(f"\n=== 전화번호 형태별 예시 ===")
    for result in results:
        print(f"{result['type']}: {result['phone']} → {result['amount']:,}원")

if __name__ == "__main__":
    test_phone_pattern_parsing()
