"""
전국대표번호 파싱 테스트
"""
import pypdf
import re

def test_star_number_parsing(pdf_path):
    """전국대표번호(**로 시작) 파싱 테스트"""
    
    # PDF 텍스트 읽기
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    # 텍스트를 라인별로 분리
    lines = text.split('\n')
    
    print("=== 전국대표번호 파싱 테스트 ===")
    
    # 전국대표번호 패턴으로 찾기
    pattern = r'\*\*\d{2}-\d{4}'
    results = []
    processed_phones = set()
    
    # 라인별로 전화번호 찾기
    for line_num, line in enumerate(lines):
        match = re.search(pattern, line)
        if match:
            phone_number = match.group(0)
            
            # 중복 체크
            if phone_number in processed_phones:
                continue
            processed_phones.add(phone_number)
            
            print(f"\n라인 {line_num}: {phone_number}")
            print(f"  라인 내용: {line.strip()}")
            
            # 이 전화번호 뒤의 15라인에서 합계 찾기
            search_lines = lines[line_num:line_num + 15]
            
            # 합계 찾기
            total_amount = None
            
            for i, search_line in enumerate(search_lines):
                search_line = search_line.strip()
                print(f"    검색라인 {i}: {search_line}")
                
                # 합계 패턴들
                total_patterns = [
                    r'합\s*계\s+(\d{1,3}(?:,\d{3})*)\s*원',  # 합계 11,652 원
                    r'합\s*계\s+(\d+)\s*원',                # 합계 11652 원
                    r'합\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 합계 11,652
                    r'소\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 소계 11,652
                    r'총\s*계\s+(\d{1,3}(?:,\d{3})*)',      # 총계 11,652
                ]
                
                for total_pattern in total_patterns:
                    total_match = re.search(total_pattern, search_line)
                    if total_match:
                        amount_str = total_match.group(1).replace(',', '')
                        if amount_str.isdigit():
                            total_amount = int(amount_str)
                            print(f"  → 합계 발견! {total_amount:,}원 (라인 {line_num + i})")
                            break
                
                if total_amount:
                    break
            
            # 합계를 못 찾았다면 구간에서 가장 큰 숫자
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
                    print(f"  → 추정 합계: {total_amount:,}원 (후보: {amounts[:3]})")
            
            if total_amount:
                results.append({
                    'phone': phone_number,
                    'total': total_amount,
                    'line_num': line_num
                })
            else:
                print(f"  → 합계 찾기 실패")
                # 구간 텍스트 출력
                section_preview = '\n'.join(search_lines[:5])
                print(f"  구간 미리보기:\n{section_preview}")
    
    print(f"\n=== 전국대표번호 파싱 결과: {len(results)}개 ===")
    for result in results:
        print(f"{result['phone']} → {result['total']:,}원")
    
    return results

if __name__ == "__main__":
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    results = test_star_number_parsing(pdf_path)
