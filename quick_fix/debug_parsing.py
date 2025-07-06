"""
파싱 과정 디버깅을 위한 상세 분석
"""
import pypdf
import re

def debug_parsing_process(pdf_path):
    """파싱 과정을 단계별로 디버깅"""
    
    # PDF 텍스트 읽기
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    # 텍스트를 라인별로 분리
    lines = text.split('\n')
    
    print("=== 파싱 과정 디버깅 ===")
    
    # 전화번호 패턴들 (메인 app.py와 동일한 순서)
    phone_patterns = [
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),  # **95-3192 (가장 단순한 패턴 먼저)
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
    ]
    
    processed_phones = set()  # 중복 방지
    all_results = []
    
    for pattern, pattern_name in phone_patterns:
        print(f"\n=== {pattern_name} 처리 시작 ===")
        
        pattern_results = []
        
        # 라인별로 전화번호 찾기
        for line_num, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                phone_number = match.group(0)
                
                # 중복 체크용 키 생성 (뒷자리 기준)
                phone_suffix = re.sub(r'^.*\*\*', '', phone_number)  # 뒷자리만 추출
                duplicate_key = phone_suffix
                
                print(f"  라인 {line_num}: {phone_number} (뒷자리: {phone_suffix})")
                
                # 중복 체크
                if duplicate_key in processed_phones:
                    print(f"    → 중복 제외 (이미 처리된 뒷자리: {duplicate_key})")
                    continue
                
                # 합계 찾기
                search_lines = lines[line_num:line_num + 15]
                total_amount = None
                
                for i, search_line in enumerate(search_lines):
                    search_line = search_line.strip()
                    
                    # 합계 패턴들
                    total_patterns = [
                        r'합\s*계\s+(\d{1,3}(?:,\d{3})*)\s*원',
                        r'합\s*계\s+(\d+)\s*원',
                        r'합\s*계\s+(\d{1,3}(?:,\d{3})*)',
                        r'소\s*계\s+(\d{1,3}(?:,\d{3})*)',
                        r'총\s*계\s+(\d{1,3}(?:,\d{3})*)',
                    ]
                    
                    for total_pattern in total_patterns:
                        total_match = re.search(total_pattern, search_line)
                        if total_match:
                            amount_str = total_match.group(1).replace(',', '')
                            if amount_str.isdigit():
                                total_amount = int(amount_str)
                                print(f"    → 합계 발견: {total_amount:,}원 (라인 {line_num + i})")
                                break
                    
                    if total_amount:
                        break
                
                # 합계를 못 찾았다면 구간에서 가장 큰 숫자 사용
                if not total_amount:
                    section_text = '\n'.join(search_lines)
                    all_numbers = re.findall(r'\d{1,3}(?:,\d{3})*', section_text)
                    amounts = []
                    for num_str in all_numbers:
                        clean_num = num_str.replace(',', '')
                        if clean_num.isdigit():
                            num = int(clean_num)
                            if 500 <= num <= 200000:
                                amounts.append(num)
                    
                    if amounts:
                        total_amount = max(amounts)
                        print(f"    → 추정 합계: {total_amount:,}원")
                
                if total_amount:
                    # 중복 방지를 위해 키 기록
                    processed_phones.add(duplicate_key)
                    
                    result = {
                        'pattern_type': pattern_name,
                        'phone': phone_number,
                        'total': total_amount,
                        'suffix': phone_suffix
                    }
                    pattern_results.append(result)
                    all_results.append(result)
                    
                    print(f"    → 파싱 성공! {phone_number} → {total_amount:,}원")
                else:
                    print(f"    → 합계 찾기 실패")
        
        print(f"{pattern_name} 결과: {len(pattern_results)}개 파싱")
    
    print(f"\n=== 전체 결과 ===")
    print(f"총 파싱된 전화번호: {len(all_results)}개")
    print(f"처리된 뒷자리 키들: {sorted(processed_phones)}")
    
    # 패턴별 통계
    pattern_counts = {}
    for result in all_results:
        pattern = result['pattern_type']
        if pattern not in pattern_counts:
            pattern_counts[pattern] = 0
        pattern_counts[pattern] += 1
    
    for pattern, count in pattern_counts.items():
        print(f"{pattern}: {count}개")

if __name__ == "__main__":
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    debug_parsing_process(pdf_path)
