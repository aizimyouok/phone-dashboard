import gspread
from google.oauth2.service_account import Credentials
import pypdf
import re
import json

# --- 설정 부분 ---
KEY_FILE_PATH = 'phone-billing-automation-ea8799f52353.json'
SPREADSHEET_NAME = 'CFC 전화번호 현황 및 요금'
PDF_FILE_PATH = 'b6fe4e6f-b0a4-4cd8-99a6-bbc5835b6a7f.pdf'

# --- 구글 시트 업데이트 함수 ---
def update_spreadsheet(master_ws, data_ws, invoice_data, billing_month):
    """파싱된 데이터를 기반으로 구글 시트를 업데이트합니다. (부분 일치 로직 적용)"""
    print("\n--- 구글 시트 업데이트 시작 ---")
    print(f"처리할 데이터: {len(invoice_data)}건")
    
    # 1. '전화번호 마스터'에서 모든 데이터를 가져와서 {전체 전화번호: 지점명} 딕셔너리로 만듭니다.
    master_records = master_ws.get_all_records()
    # 마스터 시트의 전체 전화번호와 지점명을 모두 불러옵니다.
    master_phone_list = {str(record['전화번호']).strip(): record['지점명'] for record in master_records}
    # 사용자 정보도 함께 저장
    master_user_list = {str(record['전화번호']).strip(): record.get('사용자', '') for record in master_records}
    print(f"마스터 데이터 로드: {len(master_phone_list)}개 전화번호")

    # 2. '청구내역 원본'에 기록할 데이터를 만듭니다.
    rows_to_append = []
    column_order = [
        '청구월', '지점명', '사용자', '전화번호', '기본료', '시내통화료', '이동통화료', 
        '070통화료', '정보통화료', '부가서비스료', '사용요금계', '할인액', '부가세', '최종합계'
    ]
    
    matched_count = 0
    unmatched_count = 0

    for data in invoice_data:
        pdf_phone_number = data['전화번호']  # 예: "070-XX95-3210", "02-XX98-7065", "XXXX-99-2593"
        
        # 다양한 전화번호 형태에서 뒷자리 추출
        branch_name = '미배정'
        user_name = ''
        full_phone_number = pdf_phone_number
        
        # PDF 전화번호에서 뒷자리 패턴 추출
        pdf_suffix = None
        
        # 뒷자리 패턴 추출 (다양한 형태 지원)
        suffix_patterns = [
            r'XX(\d{2}-\d{4})$',      # 070-XX95-3210, 02-XX98-7065
            r'XXXX-(\d{2}-\d{4})$',   # XXXX-99-2593  
            r'XX(\d{1,2}-\d{4})$',    # 기타 변형
            r'XX(\d{1}-\d{4})$',      # 080-XX0-7100 형태
        ]
        
        for pattern in suffix_patterns:
            match = re.search(pattern, pdf_phone_number)
            if match:
                pdf_suffix = match.group(1)
                break
        
        # 뒷자리가 추출되지 않았다면 전체 번호에서 마지막 7글자 시도
        if not pdf_suffix:
            # 숫자와 하이픈만 추출해서 뒷자리 7글자 사용
            clean_number = re.sub(r'[^0-9-]', '', pdf_phone_number)
            if len(clean_number) >= 7:
                pdf_suffix = clean_number[-7:]

        # 마스터의 전체 전화번호 목록을 순회하며 매칭합니다.
        if pdf_suffix:
            for master_phone, master_branch in master_phone_list.items():
                # 1. 정확한 뒷자리 매칭 (우선순위 1)
                if master_phone.endswith(pdf_suffix):
                    branch_name = master_branch
                    user_name = master_user_list.get(master_phone, '')
                    full_phone_number = master_phone
                    break
                
                # 2. 숫자만 비교 매칭 (우선순위 2)
                master_digits = re.sub(r'[^0-9]', '', master_phone)
                pdf_digits = re.sub(r'[^0-9]', '', pdf_suffix)
                
                if len(master_digits) >= len(pdf_digits) and master_digits.endswith(pdf_digits):
                    branch_name = master_branch
                    user_name = master_user_list.get(master_phone, '')
                    full_phone_number = master_phone
                    break

        # 매칭 결과 카운트
        if branch_name != '미배정':
            matched_count += 1
            user_display = f" - {user_name}" if user_name else ""
            print(f"  성공 {pdf_phone_number} → {full_phone_number} ({branch_name}{user_display})")
        else:
            unmatched_count += 1
            print(f"  실패 {pdf_phone_number} → 미배정 (매칭 실패)")

        # column_order 순서에 맞게 한 줄의 데이터를 리스트로 만듭니다. (전화번호, 사용자 순서)
        row = [
            billing_month,
            branch_name,
            full_phone_number,  # C열: 전화번호
            user_name,          # D열: 사용자
            data.get('기본료', 0),
            data.get('시내통화료', 0),
            data.get('이동통화료', 0),
            data.get('070통화료', 0),
            data.get('정보통화료', 0),
            data.get('부가서비스료', 0),
            data.get('사용요금계', 0),
            data.get('할인액', 0),
            data.get('부가세', 0),
            data.get('최종합계', 0)
        ]
        rows_to_append.append(row)
    
    # 매칭 결과 요약
    print(f"\n매칭 결과:")
    print(f"   성공: {matched_count}건")
    print(f"   실패: {unmatched_count}건")
    print(f"   전체: {len(invoice_data)}건")
        
    # 3. 구글 시트에 데이터를 배치별로 추가합니다. (API 제한 해결)
    if rows_to_append:
        import time
        
        # 배치 크기 설정 (한번에 최대 20행씩 업로드)
        BATCH_SIZE = 20
        DELAY_SECONDS = 2  # 배치 간 2초 대기
        
        total_rows = len(rows_to_append)
        uploaded_count = 0
        
        print(f"총 {total_rows}개의 행을 배치별로 업로드 시작... (배치크기: {BATCH_SIZE})")
        
        # 배치별로 나누어 업로드
        for i in range(0, total_rows, BATCH_SIZE):
            batch = rows_to_append[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            
            try:
                data_ws.append_rows(batch, value_input_option='USER_ENTERED')
                uploaded_count += len(batch)
                print(f"배치 {batch_num}: {len(batch)}개 행 업로드 완료 ({uploaded_count}/{total_rows})")
                
                # 마지막 배치가 아니면 대기
                if i + BATCH_SIZE < total_rows:
                    print(f"다음 배치까지 {DELAY_SECONDS}초 대기...")
                    time.sleep(DELAY_SECONDS)
                    
            except Exception as e:
                print(f"배치 {batch_num} 업로드 실패: {e}")
                # 재시도 로직
                print("10초 후 재시도...")
                time.sleep(10)
                try:
                    data_ws.append_rows(batch, value_input_option='USER_ENTERED')
                    uploaded_count += len(batch)
                    print(f"배치 {batch_num} 재시도 성공!")
                except Exception as retry_e:
                    print(f"배치 {batch_num} 재시도도 실패: {retry_e}")
                    continue
        
        print(f"업로드 완료: {uploaded_count}/{total_rows}개 행이 '청구내역 원본' 시트에 추가되었습니다.")
    else:
        print("시트에 추가할 데이터가 없습니다.")
        
    print("--- 구글 시트 업데이트 완료 ---")


# --- 데이터 파싱 및 유틸리티 함수 ---
def get_billing_month(text):
    """텍스트에서 'YYYY년 MM월'을 찾아 'YYYY-MM' 형식으로 반환합니다."""
    match = re.search(r'(\d{4})년\s*(\d{2})월', text)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return "날짜모름"

def parse_invoice_data(text):
    """PDF 텍스트에서 청구 데이터를 파싱합니다. (단순하고 확실한 버전)"""
    parsed_data = []
    
    print("=== PDF 파싱 시작 ===")
    print(f"입력 텍스트 길이: {len(text)} 문자")
    
    # 전체 텍스트에서 전화번호와 합계 금액을 직접 추출
    # 각 전화번호 패턴과 그 뒤의 합계 금액을 찾음
    
    # 전화번호 패턴들 (PDF에서 실제 나타나는 형태) - 더 단순하고 정확한 패턴
    phone_patterns = [
        (r'\*\*\d{2}-\d{4}', '전국대표번호'),           # **99-2593, **00-1631 (전국대표번호)
        (r'070\)\*\*\d{2}-\d{4}', '070번호'),      # 070)**03-2573 (070번호)
        (r'02\)\*\*\d{2}-\d{4}', '02번호'),       # 02)**35-6493 (02번호)
        (r'080\)\*\*\d{1}-\d{4}', '080번호'),      # 080)**0-7100 (080번호)
    ]
    
    print("=== 패턴별 매칭 결과 ===")
    total_parsed = 0
    # 각 패턴별로 전화번호를 찾고 데이터를 추출
    for pattern, pattern_name in phone_patterns:
        matches = list(re.finditer(pattern, text))
        print(f"{pattern_name} 패턴 '{pattern}': {len(matches)}개 매칭")
        pattern_parsed = 0
        
        for i, match in enumerate(matches):
            phone_number = match.group(0)  # 전체 매칭된 문자열
            print(f"  {i+1}. 발견된 전화번호: {phone_number}")
            
            # 전화번호 위치에서 그 뒤의 텍스트를 가져와서 합계 금액 찾기
            start_pos = match.end()
            remaining_text = text[start_pos:start_pos + 2000]  # 전화번호 뒤 2000자
            
            # 해당 전화번호의 합계 금액 찾기 (가장 가까운 "합계 XXX원")
            total_match = re.search(r'합계\s+([\d,]+)\s*원', remaining_text)
            
            if total_match:
                total_amount = int(total_match.group(1).replace(',', ''))
                print(f"     → 합계: {total_amount}원")
                
                # 전화번호와 합계 사이의 텍스트에서 세부 금액 추출
                detail_text = remaining_text[:total_match.end()]
                amounts = extract_amounts_from_content(detail_text)
                amounts['최종합계'] = total_amount
                amounts['전화번호'] = phone_number
                
                parsed_data.append(amounts)
                pattern_parsed += 1
                total_parsed += 1
                print(f"     → 파싱 완료: {phone_number} ({total_amount}원)")
            else:
                print(f"     → 합계 금액 찾을 수 없음 - 건너뜀")
        
        print(f"  {pattern_name}: {pattern_parsed}/{len(matches)}개 파싱 성공")
        print()
    
    print(f"=== 파싱 완료: 총 {total_parsed}개 전화번호 추출 (발견: 133개 중) ===")
    return parsed_data

def extract_phone_number_from_content(content):
    """텍스트에서 전화번호를 추출합니다 (개선된 패턴)"""
    # 다양한 전화번호 패턴들 (PDF 실제 형태에 맞게)
    phone_patterns = [
        # 전국대표번호: **99-2593, **00-1631
        r'\*\*(\d{2}-\d{4})',
        # 070 번호: 070)**03-2573
        r'070\)\*\*(\d{2}-\d{4})',
        # 02 번호: 02)**35-6493  
        r'02\)\*\*(\d{2}-\d{4})',
        # 080 번호: 080)**0-7100
        r'080\)\*\*(\d{1}-\d{4})',
        # 일반 지역번호: 031)**12-3456 등
        r'(\d{2,3})\)\*\*(\d{2}-\d{4})',
        # 4자리 번호: 1588)**12-3456 등  
        r'(\d{4})\)\*\*(\d{1,2}-\d{4})',
        # 단순한 번호들 (백업용)
        r'(\d{2,4})-(\d{4})',
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, content)
        if match:
            if pattern.startswith(r'\*\*'):
                # 전국대표번호
                return f"**{match.group(1)}"
            elif '070' in pattern:
                # 070 번호
                return f"070)**{match.group(1)}"
            elif '02' in pattern:
                # 02 번호  
                return f"02)**{match.group(1)}"
            elif '080' in pattern:
                # 080 번호
                return f"080)**{match.group(1)}"
            elif len(match.groups()) == 2:
                # 일반 지역번호
                return f"{match.group(1)})**{match.group(2)}"
            else:
                # 기타
                return match.group(0)
    
    return None

def extract_amounts_from_content(content):
    """텍스트에서 각종 요금 정보를 추출합니다"""
    def find_amount(pattern):
        match = re.search(pattern, content)
        if match:
            amount_str = match.group(1).replace(',', '')
            return int(amount_str) if amount_str.isdigit() else 0
        return 0
    
    return {
        '기본료': find_amount(r'(?:인터넷전화기본료|전국대표번호부가이용료|웹팩스\s*기본료|Biz\s*ARS)\s+([\d,]+)'),
        '시내통화료': find_amount(r'시내통화료\s+([\d,]+)'),
        '이동통화료': find_amount(r'이동통화료\s+([\d,]+)'),
        '070통화료': find_amount(r'인터넷전화통화료\(070\)\s+([\d,]+)'),
        '정보통화료': find_amount(r'정보통화료\s+([\d,]+)'),
        '부가서비스료': find_amount(r'부가서비스이용료\s+([\d,]+)'),
        '사용요금계': find_amount(r'사용요금\s*계\s+([\d,]+)'),
        '할인액': find_amount(r'할인\s+-?([\d,]+)'),
        '부가세': find_amount(r'부가가치세\(세금\)\*?\s+([\d,]+)'),
    }
                # 고정 접두사가 있는 경우
                suffix = match.group(1)
                phone_number = format_str.format(suffix)
            break
    
    if not phone_number:
        return None
    
    def find_amount(patterns):
        """여러 패턴을 시도해서 금액을 찾습니다"""
        if isinstance(patterns, str):
            patterns = [patterns]
        
        for pattern in patterns:
            match = re.search(pattern, section)
            if match:
                return int(match.group(1).replace(',', ''))
        return 0
    
    # 서비스 타입에 따른 기본료 패턴 결정
    basic_fee_patterns = []
    if '전국대표번호' in service_type:
        basic_fee_patterns = [
            r'전국대표번호부가이용료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    elif '웹팩스' in service_type:
        basic_fee_patterns = [
            r'웹팩스 기본료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    else:
        basic_fee_patterns = [
            r'인터넷전화기본료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    
    # 부가서비스료 패턴도 서비스별로 구분
    vas_fee_patterns = [
        r'부가서비스이용료\s+([\d,]+)',
        r'전국대표번호부가이용료\s+([\d,]+)',
        r'웹팩스 국내이용료\s+([\d,]+)',
        r'Biz ARS\s+([\d,]+)',
        r'착신과금 접속료\s+([\d,]+)',
        r'부가서비스료\s+([\d,]+)'
    ]
    
    data = {
        '전화번호': phone_number,
        '기본료': find_amount(basic_fee_patterns),
        '시내통화료': find_amount(r'시내통화료\s+([\d,]+)'),
        '이동통화료': find_amount(r'이동통화료\s+([\d,]+)'),
        '070통화료': find_amount([
            r'인터넷전화통화료\(070\)\s+([\d,]+)',
            r'국제통화료\s+([\d,]+)'
        ]),
        '정보통화료': find_amount(r'정보통화료\s+([\d,]+)'),
        '부가서비스료': find_amount(vas_fee_patterns),
        '사용요금계': find_amount([
            r'사용요금 계\s+([\d,]+)',
            r'사용요금계\s+([\d,]+)'
        ]),
        '할인액': find_amount([
            r'할인\s+-([\d,]+)',
            r'할인액\s+-([\d,]+)'
        ]),
        '부가세': find_amount([
            r'부가가치세\(세금\)\*\s+([\d,]+)',
            r'부가세\s+([\d,]+)'
        ]),
        '최종합계': find_amount([
            r'합계\s+([\d,]+)',
            r'최종합계\s+([\d,]+)'
        ])
    }
    
    return data

def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = pypdf.PdfReader(pdf_file)
            full_text = "".join(page.extract_text() for page in reader.pages)
            
            # 디버깅: 추출된 텍스트의 일부를 출력
            print("=== PDF 텍스트 추출 결과 ===")
            print(f"전체 텍스트 길이: {len(full_text)} 문자")
            print("처음 1000문자:")
            print(full_text[:1000])
            print("=" * 50)
            
            # 전화번호 패턴이 있는지 직접 확인
            import re
            patterns_to_check = [
                (r'\*\*\d{2}-\d{4}', '전국대표번호'),
                (r'02\)\*\*\d{2}-\d{4}', '02번호'),
                (r'070\)\*\*\d{2}-\d{4}', '070번호'),
                (r'080\)\*\*\d{1}-\d{4}', '080번호'),
            ]
            
            print("텍스트에서 발견된 전화번호 패턴:")
            for pattern, name in patterns_to_check:
                matches = re.findall(pattern, full_text)
                print(f"  {name}: {len(matches)}개 - {matches[:5]}")  # 최대 5개까지만 출력
            print("=" * 50)
            
            return full_text
    except Exception as e:
        print(f"PDF 읽기 에러: {e}")
        return None

def get_spreadsheet():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(KEY_FILE_PATH, scopes=scope)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open(SPREADSHEET_NAME)
        master_ws = spreadsheet.worksheet("전화번호 마스터")
        data_ws = spreadsheet.worksheet("청구내역 원본")
        return master_ws, data_ws
    except Exception as e:
        print(f"구글 시트 연결 에러: {e}")
        return None, None

# --- 메인 실행 부분 ---
if __name__ == "__main__":
    print("스크립트를 시작합니다...")
    master_worksheet, data_worksheet = get_spreadsheet()
    
    if master_worksheet and data_worksheet:
        pdf_text = read_pdf(PDF_FILE_PATH)
        
        if pdf_text:
            invoice_data = parse_invoice_data(pdf_text)
            billing_month = get_billing_month(pdf_text)
            
            if invoice_data:
                print(f"\n파싱 결과:")
                print(f"   청구월: {billing_month}")
                print(f"   추출된 회선 수: {len(invoice_data)}")
                print(f"   추출된 전화번호들:")
                for i, data in enumerate(invoice_data[:10], 1):  # 최대 10개까지 출력
                    print(f"     {i}. {data['전화번호']} (합계: {data['최종합계']:,}원)")
                if len(invoice_data) > 10:
                    print(f"     ... 외 {len(invoice_data) - 10}개 더")
                
                update_spreadsheet(master_worksheet, data_worksheet, invoice_data, billing_month)
                print("\n모든 작업이 성공적으로 완료되었습니다!")
            else:
                print("PDF에서 유효한 요금 데이터를 찾지 못했습니다.")
        else:
            print("PDF 파일을 읽을 수 없습니다.")
    else:
        print("구글 시트에 연결할 수 없습니다.")
