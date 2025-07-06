"""
단순하고 확실한 PDF 파싱 - 복잡한 패턴 매칭 없이 숫자만 추출
"""
import pypdf
import re

def simple_parse_pdf(pdf_path):
    """PDF에서 전화번호와 가장 가까운 큰 숫자를 추출"""
    
    # PDF 텍스트 읽기
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    print(f"PDF 텍스트 길이: {len(text)}자")
    
    # 전화번호 패턴들
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
        (r'(?<!\d\)\*)\*\*\d{2}-\d{4}', '전국대표번호'),
    ]
    
    results = []
    
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        print(f"\n{pattern_name}: {len(matches)}개 발견")
        
        for i, match in enumerate(matches[:5], 1):  # 최대 5개만 처리
            phone = match.group(0)
            start = match.start()
            end = match.end()
            
            # 전화번호 주변 2000자 텍스트 추출 (앞뒤 1000자씩)
            context_start = max(0, start - 1000)
            context_end = min(len(text), end + 1000)
            context = text[context_start:context_end]
            
            # 해당 구간에서 모든 숫자 찾기 (3자리 이상)
            numbers = re.findall(r'\d{3,}', context)
            # 쉼표 포함 숫자도 찾기
            comma_numbers = re.findall(r'\d{1,3}(?:,\d{3})+', context)
            
            all_numbers = []
            for num in numbers + comma_numbers:
                clean_num = num.replace(',', '')
                if clean_num.isdigit():
                    all_numbers.append(int(clean_num))
            
            if all_numbers:
                # 가장 큰 숫자를 합계로 사용 (단, 너무 크지 않은)
                reasonable_amounts = [n for n in all_numbers if 100 <= n <= 1000000]
                if reasonable_amounts:
                    total_amount = max(reasonable_amounts)
                    
                    results.append({
                        'pattern_type': pattern_name,
                        'phone': phone,
                        'total': total_amount,
                        'all_numbers': sorted(reasonable_amounts, reverse=True)[:5]
                    })
                    
                    print(f"  {i}. {phone} -> {total_amount:,}원 (후보: {reasonable_amounts[:3]})")
                else:
                    print(f"  {i}. {phone} -> 적절한 금액 없음 (모든 숫자: {all_numbers[:5]})")
            else:
                print(f"  {i}. {phone} -> 숫자 없음")
    
    print(f"\n총 {len(results)}개 전화번호 파싱 성공!")
    return results

if __name__ == "__main__":
    # PDF 파일 경로
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    print("=== 단순 PDF 파싱 테스트 ===")
    results = simple_parse_pdf(pdf_path)
    
    print(f"\n=== 결과 요약 ===")
    for result in results:
        print(f"{result['pattern_type']}: {result['phone']} -> {result['total']:,}원")
