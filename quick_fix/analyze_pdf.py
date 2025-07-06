"""
PDF를 라인별로 분석해서 패턴 찾기
"""
import pypdf
import re

def analyze_pdf_structure(pdf_path):
    """PDF 구조를 라인별로 분석"""
    
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    
    lines = text.split('\n')
    print(f"총 {len(lines)}개 라인")
    
    # 전화번호가 포함된 라인 찾기
    phone_lines = []
    for i, line in enumerate(lines):
        if re.search(r'(\*\*\d{2}-\d{4}|070\)\*\*\d{2}-\d{4}|02\)\*\*\d{2}-\d{4}|080\)\*\*\d{1}-\d{4})', line):
            phone_lines.append((i, line.strip()))
    
    print(f"\n전화번호 포함 라인: {len(phone_lines)}개")
    
    # 각 전화번호 라인과 그 주변 라인들 출력
    for i, (line_num, line) in enumerate(phone_lines[:10]):  # 처음 10개만
        print(f"\n=== 전화번호 {i+1} ===")
        print(f"라인 {line_num}: {line}")
        
        # 앞뒤 3줄씩 출력
        start = max(0, line_num - 3)
        end = min(len(lines), line_num + 4)
        
        print("주변 텍스트:")
        for j in range(start, end):
            marker = " >>> " if j == line_num else "     "
            print(f"{marker}{j:3d}: {lines[j].strip()}")
        
        # 이 구간에서 숫자 찾기
        context = '\n'.join(lines[start:end])
        amounts = re.findall(r'\d{1,3}(?:,\d{3})*', context)
        print(f"발견된 금액들: {amounts}")

if __name__ == "__main__":
    pdf_path = r"C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf"
    
    print("=== PDF 구조 분석 ===")
    analyze_pdf_structure(pdf_path)
