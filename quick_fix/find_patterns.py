"""
PDF에서 모든 전화번호 패턴 찾기 (02, 전국대표번호 포함)
"""
import pypdf
import re

def find_all_phone_patterns(pdf_path):
    """PDF에서 모든 전화번호 패턴을 찾아서 분석"""
    
    # PDF 텍스트 읽기
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    print(f"PDF 텍스트 길이: {len(text)}자")
    
    # 다양한 전화번호 패턴들 테스트
    patterns_to_test = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
        (r'\*\*\d{2}-\d{4}', '전국대표번호(단순)'),
        (r'(?<!\d\)\*)\*\*\d{2}-\d{4}', '전국대표번호(복잡)'),
        (r'\d{2,4}\)\*\*\d{1,2}-\d{4}', '일반지역번호'),
        (r'[0-9*-]{10,}', '모든번호형태'),
    ]
    
    print("\n=== 모든 패턴 검색 결과 ===")
    
    for pattern, name in patterns_to_test:
        matches = re.findall(pattern, text)
        print(f"\n{name}: {len(matches)}개")
        
        if matches:
            # 중복 제거
            unique_matches = list(set(matches))
            print(f"  고유 번호: {len(unique_matches)}개")
            
            # 샘플 출력 (최대 10개)
            for i, match in enumerate(unique_matches[:10], 1):
                print(f"  {i:2d}. {match}")
            
            if len(unique_matches) > 10:
                print(f"  ... 외 {len(unique_matches) - 10}개 더")

    # **로 시작하는 패턴을 더 자세히 분석
    print(f"\n=== **로 시작하는 모든 패턴 분석 ===")
    star_patterns = re.findall(r'\*\*[0-9-]+', text)
    unique_stars = list(set(star_patterns))
    print(f"**로 시작하는 패턴: {len(unique_stars)}개")
    
    for pattern in unique_stars[:20]:  # 최대 20개
        print(f"  {pattern}")
    
    # 02로 시작하는 패턴 분석
    print(f"\n=== 02로 시작하는 모든 패턴 분석 ===")
    zero_two_patterns = re.findall(r'02[^a-zA-Z]*\d+[-0-9*]+', text)
    unique_02 = list(set(zero_two_patterns))
    print(f"02로 시작하는 패턴: {len(unique_02)}개")
    
    for pattern in unique_02[:20]:  # 최대 20개
        print(f"  {pattern}")

if __name__ == "__main__":
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    print("=== 모든 전화번호 패턴 검색 ===")
    find_all_phone_patterns(pdf_path)
