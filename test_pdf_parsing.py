import pypdf
import re

def get_billing_month(text):
    """텍스트에서 'YYYY년 MM월'을 찾아 'YYYY-MM' 형식으로 반환합니다."""
    match = re.search(r'(\d{4})년\s*(\d{2})월', text)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return "날짜모름"

def parse_invoice_data(text):
    """PDF 텍스트에서 청구 데이터를 파싱합니다. (디버깅 강화 버전)"""
    parsed_data = []
    
    print("=== PDF 파싱 시작 ===")
    print(f"입력 텍스트 길이: {len(text)} 문자")
    
    # 전화번호 패턴들 (PDF에서 실제 나타나는 형태)
    phone_patterns = [
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),           # **99-2593, **00-1631 (전국대표번호)
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),      # 070)**03-2573 (070번호)
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),       # 02)**35-6493 (02번호)
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),      # 080)**0-7100 (080번호)
    ]
    
    print("=== 텍스트에서 발견된 전화번호 패턴 ===")
    for pattern, name in phone_patterns:
        matches = re.findall(pattern, text)
        print(f"{name}: {len(matches)}개 - {matches[:5]}")  # 최대 5개까지만 출력
    print()
    
    print("=== 패턴별 매칭 및 합계 찾기 상세 분석 ===")
    total_parsed = 0
    
    # 각 패턴별로 전화번호를 찾고 데이터를 추출
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        print(f"\n{pattern_name} 패턴 '{pattern}': {len(matches)}개 매칭")
        pattern_parsed = 0
        
        for i, match in enumerate(matches):
            phone_number = match.group(0)  # 전체 매칭된 문자열
            print(f"  {i+1}. 발견된 전화번호: {phone_number}")
            
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
                        
                        # 간단한 데이터 구조로 저장
                        parsed_data.append({
                            '전화번호': phone_number,
                            '최종합계': total_amount,
                            '패턴': pattern_name,
                            '합계패턴': total_pattern,
                            '검색범위': search_range
                        })
                        pattern_parsed += 1
                        total_parsed += 1
                        total_found = True
                        break
                
                if total_found:
                    break
            
            if not total_found:
                print(f"     → 합계 금액 찾을 수 없음")
                # 근처 텍스트 샘플 출력
                sample_text = text[start_pos:start_pos + 500]
                print(f"     → 근처 텍스트 샘플: {sample_text[:200]}...")
        
        print(f"  {pattern_name}: {pattern_parsed}/{len(matches)}개 파싱 성공")
    
    print(f"\n=== 파싱 완료: 총 {total_parsed}개 전화번호 추출 ===")
    
    # 결과 요약
    print("\n=== 파싱 결과 요약 ===")
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
    
    print("PDF 파싱 테스트 시작...")
    
    pdf_text = read_pdf(pdf_file_path)
    if pdf_text:
        invoice_data = parse_invoice_data(pdf_text)
        billing_month = get_billing_month(pdf_text)
        
        print(f"\n=== 최종 결과 ===")
        print(f"청구월: {billing_month}")
        print(f"총 추출된 전화번호: {len(invoice_data)}개")
        
        if invoice_data:
            print("\n상세 결과:")
            for data in invoice_data:
                print(f"  {data['전화번호']} - {data['최종합계']:,}원 ({data['패턴']})")
    else:
        print("PDF 파일을 읽을 수 없습니다.")
