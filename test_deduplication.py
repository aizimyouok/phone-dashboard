import pypdf
import re

def parse_invoice_data_improved(text):
    """PDF 텍스트에서 청구 데이터를 파싱합니다. (중복 제거 및 개선된 버전)"""
    parsed_data = []
    processed_suffixes = set()  # 중복 방지를 위한 세트
    
    print("=== PDF 파싱 시작 (개선된 버전) ===")
    print(f"입력 텍스트 길이: {len(text)} 문자")
    
    # 전화번호 패턴들 우선순위 순으로 정렬 (더 구체적인 패턴을 먼저)
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),      # 070)**03-2573 (070번호) - 우선순위 1
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),       # 02)**35-6493 (02번호) - 우선순위 2  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),      # 080)**0-7100 (080번호) - 우선순위 3
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),           # **99-2593, **00-1631 (전국대표번호) - 우선순위 4
    ]
    
    print("=== 텍스트에서 발견된 전화번호 패턴 ===")
    for pattern, name in phone_patterns:
        matches = re.findall(pattern, text)
        print(f"{name}: {len(matches)}개 - {matches[:5]}")
    print()
    
    print("=== 패턴별 매칭 및 중복 제거 상세 분석 ===")
    total_parsed = 0
    
    # 각 패턴별로 전화번호를 찾고 데이터를 추출
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        print(f"\n{pattern_name} 패턴 '{pattern}': {len(matches)}개 매칭")
        pattern_parsed = 0
        pattern_skipped = 0
        
        for i, match in enumerate(matches):
            phone_number = match.group(0)
            
            # 뒷자리 추출로 중복 체크
            suffix = None
            if pattern_name == '070번호':
                suffix = phone_number.replace('070)**', '')  # 03-2573
            elif pattern_name == '02번호':
                suffix = phone_number.replace('02)**', '')   # 35-6493
            elif pattern_name == '080번호':
                suffix = phone_number.replace('080)**', '')  # 0-7100
            elif pattern_name == '전국대표번호':
                suffix = phone_number.replace('**', '')      # 99-2593
            
            # 중복 체크
            if suffix in processed_suffixes:
                print(f"  {i+1}. {phone_number} → 중복 (뒷자리: {suffix}) - 건너뜀")
                pattern_skipped += 1
                continue
            
            print(f"  {i+1}. 발견된 전화번호: {phone_number} (뒷자리: {suffix})")
            
            # 전화번호 위치에서 그 뒤의 텍스트를 가져와서 합계 금액 찾기
            start_pos = match.end()
            
            # 다양한 범위로 합계 금액 찾기 시도
            for search_range in [2000, 5000, 10000]:
                remaining_text = text[start_pos:start_pos + search_range]
                
                # 다양한 합계 패턴 시도
                total_patterns = [
                    r'합계\s+([\d,]+)\s*원',
                    r'합 계\s+([\d,]+)\s*원', 
                    r'총합계\s+([\d,]+)\s*원',
                    r'소계\s+([\d,]+)\s*원',
                    r'계\s+([\d,]+)\s*원',
                ]
                
                total_found = False
                for total_pattern in total_patterns:
                    total_match = re.search(total_pattern, remaining_text)
                    if total_match:
                        total_amount = int(total_match.group(1).replace(',', ''))
                        print(f"     → 합계: {total_amount}원 (패턴: '{total_pattern}', 범위: {search_range}자)")
                        
                        # 중복 방지를 위해 뒷자리 기록
                        processed_suffixes.add(suffix)
                        
                        # 간단한 데이터 구조로 저장
                        parsed_data.append({
                            '전화번호': phone_number,
                            '최종합계': total_amount,
                            '패턴': pattern_name,
                            '합계패턴': total_pattern,
                            '검색범위': search_range,
                            '뒷자리': suffix
                        })
                        pattern_parsed += 1
                        total_parsed += 1
                        total_found = True
                        break
                
                if total_found:
                    break
            
            if not total_found:
                print(f"     → 합계 금액 찾을 수 없음")
        
        print(f"  {pattern_name}: {pattern_parsed}개 파싱 성공, {pattern_skipped}개 중복 제외")
    
    print(f"\n=== 파싱 완료: 총 {total_parsed}개 전화번호 추출 (중복 제거됨) ===")
    
    # 결과 요약
    print("\n=== 파싱 결과 요약 (중복 제거됨) ===")
    for data in parsed_data:
        print(f"{data['전화번호']} ({data['패턴']}) - {data['최종합계']:,}원")
    
    return parsed_data

def read_pdf(file_path):
    """PDF 파일을 읽고 텍스트를 추출합니다."""
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = pypdf.PdfReader(pdf_file)
            full_text = "".join(page.extract_text() for page in reader.pages)
            
            print("=== PDF 텍스트 추출 결과 ===")
            print(f"전체 텍스트 길이: {len(full_text)} 문자")
            
            return full_text
    except Exception as e:
        print(f"PDF 읽기 에러: {e}")
        return None

# 메인 실행
if __name__ == "__main__":
    pdf_file_path = r'C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf'
    
    print("PDF 파싱 테스트 시작 (중복 제거 버전)...")
    
    pdf_text = read_pdf(pdf_file_path)
    if pdf_text:
        invoice_data = parse_invoice_data_improved(pdf_text)
        
        print(f"\n=== 최종 결과 (중복 제거됨) ===")
        print(f"총 추출된 전화번호: {len(invoice_data)}개")
        
        if invoice_data:
            print("\n상세 결과:")
            for data in invoice_data:
                print(f"  {data['전화번호']} - {data['최종합계']:,}원 ({data['패턴']}, 뒷자리: {data['뒷자리']})")
    else:
        print("PDF 파일을 읽을 수 없습니다.")
