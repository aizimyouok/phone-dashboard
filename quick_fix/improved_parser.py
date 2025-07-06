"""
개선된 PDF 파싱 - 전화번호별로 정확한 합계 금액 추출
"""
import pypdf
import re

def improved_parse_pdf(pdf_path):
    """각 전화번호별로 정확한 합계 금액을 추출"""
    
    # PDF 텍스트 읽기
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    print(f"PDF 텍스트 길이: {len(text)}자")
    
    # 텍스트를 라인별로 분리
    lines = text.split('\n')
    
    # 전화번호 패턴들
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
        (r'(?<!\d\)\*)\*\*\d{2}-\d{4}', '전국대표번호'),
    ]
    
    results = []
    processed_phones = set()  # 중복 방지
    
    for pattern, pattern_name in phone_patterns:
        print(f"\n=== {pattern_name} 처리 ===")
        
        # 라인별로 전화번호 찾기
        for line_num, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                phone = match.group(0)
                
                # 중복 체크 (뒷자리 기준)
                phone_suffix = re.sub(r'^.*\*\*', '', phone)  # 뒷자리만 추출
                if phone_suffix in processed_phones:
                    continue
                processed_phones.add(phone_suffix)
                
                print(f"라인 {line_num}: {phone}")
                
                # 이 전화번호 뒤의 10-15라인에서 합계 찾기 (개별 전화번호 구간)
                search_lines = lines[line_num:line_num + 15]
                
                # 다양한 합계 패턴으로 찾기
                total_amount = None
                details = {}
                
                for i, search_line in enumerate(search_lines):
                    search_line = search_line.strip()
                    
                    # 합계 패턴들 (더 유연하게)
                    total_patterns = [
                        r'합\s*계\s+(\d{1,3}(?:,\d{3})*)\s*원',  # 합계 11,652 원
                        r'합\s*계\s+(\d+)\s*원',                # 합계 11652 원
                        r'합\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 합계 11,652 (원 없이)
                        r'소\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 소계 11,652
                        r'총\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 총계 11,652
                    ]
                    
                    for total_pattern in total_patterns:
                        total_match = re.search(total_pattern, search_line)
                        if total_match:
                            amount_str = total_match.group(1).replace(',', '')
                            if amount_str.isdigit():
                                total_amount = int(amount_str)
                                print(f"  → 합계 발견 (라인 {line_num + i}): {total_amount:,}원")
                                break
                    
                    if total_amount:
                        break
                    
                    # 합계를 못 찾았다면 기본료, 통화료 등을 개별적으로 찾아서 합산
                    # 기본료 찾기
                    if '기본료' in search_line:
                        basic_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', search_line)
                        if basic_match:
                            details['기본료'] = int(basic_match.group(1).replace(',', ''))
                    
                    # 통화료 찾기
                    if '통화료' in search_line:
                        call_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', search_line)
                        if call_match:
                            details['통화료'] = int(call_match.group(1).replace(',', ''))
                    
                    # 부가서비스료 찾기
                    if '부가서비스' in search_line:
                        vas_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', search_line)
                        if vas_match:
                            details['부가서비스료'] = int(vas_match.group(1).replace(',', ''))
                
                # 합계를 찾지 못했다면 개별 항목들의 합으로 계산
                if not total_amount and details:
                    total_amount = sum(details.values())
                    print(f"  → 개별 항목 합산: {total_amount:,}원 (항목: {details})")
                
                # 그래도 없다면 해당 구간에서 가장 큰 숫자 사용 (마지막 수단)
                if not total_amount:
                    section_text = '\n'.join(search_lines)
                    all_numbers = re.findall(r'\d{1,3}(?:,\d{3})*', section_text)
                    amounts = []
                    for num_str in all_numbers:
                        clean_num = num_str.replace(',', '')
                        if clean_num.isdigit():
                            num = int(clean_num)
                            if 500 <= num <= 200000:  # 합리적인 범위
                                amounts.append(num)
                    
                    if amounts:
                        total_amount = max(amounts)
                        print(f"  → 추정 합계 (최대값): {total_amount:,}원")
                
                if total_amount:
                    results.append({
                        'pattern_type': pattern_name,
                        'phone': phone,
                        'total': total_amount,
                        'line_num': line_num,
                        'details': details
                    })
                else:
                    print(f"  → 합계 찾기 실패")
                    # 디버깅용: 해당 구간 텍스트 출력
                    section_text = '\n'.join(search_lines[:10])
                    print(f"  구간 텍스트: {section_text[:200]}...")
    
    print(f"\n=== 파싱 완료: 총 {len(results)}개 전화번호 ===")
    return results

def print_results(results):
    """결과를 보기 좋게 출력"""
    print("\n=== 파싱 결과 상세 ===")
    
    total_sum = 0
    for i, result in enumerate(results, 1):
        print(f"{i:2d}. {result['pattern_type']:8s} {result['phone']:15s} → {result['total']:>8,}원")
        total_sum += result['total']
    
    print(f"\n총 합계: {total_sum:,}원")
    print(f"평균 금액: {total_sum // len(results) if results else 0:,}원")

if __name__ == "__main__":
    # PDF 파일 경로
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    print("=== 개선된 PDF 파싱 테스트 ===")
    results = improved_parse_pdf(pdf_path)
    print_results(results)
