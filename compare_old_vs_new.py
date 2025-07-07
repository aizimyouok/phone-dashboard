import pypdf
import re

# 기존 버전 (뒷자리 기준 중복 제거)
def parse_invoice_data_old(text):
    """기존 PDF 텍스트 파싱 함수 (뒷자리 기준)"""
    parsed_data = []
    processed_suffixes = set()  # 뒷자리 기준 중복 체크
    
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),
    ]
    
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        
        for match in matches:
            phone_number = match.group(0)
            
            # 기존 방식: 뒷자리 추출로 중복 체크
            suffix = None
            if pattern_name == '070번호':
                suffix = phone_number.replace('070)**', '')
            elif pattern_name == '02번호':
                suffix = phone_number.replace('02)**', '')
            elif pattern_name == '080번호':
                suffix = phone_number.replace('080)**', '')
            elif pattern_name == '전국대표번호':
                suffix = phone_number.replace('**', '')
            
            if suffix in processed_suffixes:
                continue
            
            # 합계 찾기
            start_pos = match.end()
            for search_range in [2000, 5000, 10000]:
                remaining_text = text[start_pos:start_pos + search_range]
                total_match = re.search(r'합계\s+([\d,]+)\s*원', remaining_text)
                if total_match:
                    total_amount = int(total_match.group(1).replace(',', ''))
                    processed_suffixes.add(suffix)
                    parsed_data.append({
                        '전화번호': phone_number,
                        '최종합계': total_amount
                    })
                    break
                    
    return parsed_data

# 수정된 버전 (전체 번호 기준 중복 제거)
def parse_invoice_data_new(text):
    """수정된 PDF 텍스트 파싱 함수 (전체 번호 기준)"""
    parsed_data = []
    processed_full_numbers = set()  # 전체 번호 기준 중복 체크
    
    phone_patterns = [
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),  
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),
    ]
    
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        
        for match in matches:
            phone_number = match.group(0)
            
            # 수정된 방식: 전체 전화번호로 중복 체크
            if phone_number in processed_full_numbers:
                continue
            
            # 합계 찾기
            start_pos = match.end()
            for search_range in [2000, 5000, 10000]:
                remaining_text = text[start_pos:start_pos + search_range]
                total_match = re.search(r'합계\s+([\d,]+)\s*원', remaining_text)
                if total_match:
                    total_amount = int(total_match.group(1).replace(',', ''))
                    processed_full_numbers.add(phone_number)
                    parsed_data.append({
                        '전화번호': phone_number,
                        '최종합계': total_amount
                    })
                    break
                    
    return parsed_data

def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = pypdf.PdfReader(pdf_file)
            full_text = "".join(page.extract_text() for page in reader.pages)
            return full_text
    except Exception as e:
        return None

def compare_results(old_data, new_data):
    """기존 결과와 수정된 결과를 비교"""
    print(f"\n{'='*60}")
    print("[비교분석] 기존 vs 수정된 버전 비교")
    print(f"{'='*60}")
    
    # 번호별로 딕셔너리로 변환
    old_dict = {d['전화번호']: d['최종합계'] for d in old_data}
    new_dict = {d['전화번호']: d['최종합계'] for d in new_data}
    
    print(f"기존 버전: {len(old_data)}개 번호")
    print(f"수정 버전: {len(new_data)}개 번호")
    print(f"차이: {len(new_data) - len(old_data):+d}개")
    
    # 모든 번호 수집
    all_numbers = set(old_dict.keys()) | set(new_dict.keys())
    
    # 상태별 분류
    same_numbers = []      # 동일한 번호
    changed_numbers = []   # 금액 변경된 번호  
    missing_numbers = []   # 수정 버전에서 사라진 번호
    new_numbers = []       # 수정 버전에서 추가된 번호
    
    for number in sorted(all_numbers):
        old_amount = old_dict.get(number, 0)
        new_amount = new_dict.get(number, 0)
        
        if old_amount > 0 and new_amount > 0:
            if old_amount == new_amount:
                same_numbers.append((number, old_amount))
            else:
                changed_numbers.append((number, old_amount, new_amount))
        elif old_amount > 0 and new_amount == 0:
            missing_numbers.append((number, old_amount))
        elif old_amount == 0 and new_amount > 0:
            new_numbers.append((number, new_amount))
    
    print(f"\n[동일] 동일한 번호: {len(same_numbers)}개")
    if len(same_numbers) <= 10:  # 10개 이하면 모두 표시
        for number, amount in same_numbers:
            print(f"   {number}: {amount:,}원")
    else:  # 많으면 몇 개만 표시
        for number, amount in same_numbers[:5]:
            print(f"   {number}: {amount:,}원")
        print(f"   ... 외 {len(same_numbers)-5}개 더")
    
    if changed_numbers:
        print(f"\n[변경] 금액 변경된 번호: {len(changed_numbers)}개")
        for number, old_amount, new_amount in changed_numbers:
            status = "[개선]" if number in ['070)**60-0511', '070)**36-2736'] else "[변경]"
            print(f"   {status} {number}: {old_amount:,}원 → {new_amount:,}원")
    
    if missing_numbers:
        print(f"\n[사라짐] 사라진 번호: {len(missing_numbers)}개")
        for number, amount in missing_numbers:
            print(f"   {number}: {amount:,}원 (기존에만 있음)")
    
    if new_numbers:
        print(f"\n[추가] 새로 추가된 번호: {len(new_numbers)}개")
        for number, amount in new_numbers:
            print(f"   {number}: {amount:,}원 (수정 버전에만 있음)")
    
    return len(missing_numbers), len(changed_numbers)

# 테스트 실행
if __name__ == "__main__":
    pdf_file_path = r'C:\Users\aizim\OneDrive\Desktop\pdf-automation\b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf'
    
    print("기존 vs 수정된 파싱 로직 비교 테스트...")
    
    pdf_text = read_pdf(pdf_file_path)
    if pdf_text:
        print("기존 버전 실행 중...")
        old_data = parse_invoice_data_old(pdf_text)
        
        print("수정된 버전 실행 중...")
        new_data = parse_invoice_data_new(pdf_text)
        
        missing_count, changed_count = compare_results(old_data, new_data)
        
        print(f"\n{'='*60}")
        print("[최종결론]:")
        if missing_count == 0 and changed_count <= 2:
            print("[안전] 수정이 안전합니다! 기존 번호들은 그대로 유지됩니다.")
        elif missing_count > 0:
            print(f"[주의] {missing_count}개 번호가 사라졌습니다. 추가 검토 필요.")
        else:
            print("[변경] 변경사항이 있지만 대부분 개선된 것으로 보입니다.")
            
    else:
        print("PDF 파일을 읽을 수 없습니다.")
