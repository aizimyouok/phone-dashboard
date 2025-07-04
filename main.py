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

        # column_order 순서에 맞게 한 줄의 데이터를 리스트로 만듭니다. (사용자 열 추가)
        row = [
            billing_month,
            branch_name,
            user_name,  # 사용자 열 추가!
            full_phone_number, # 마스터에서 찾은 전체 번호로 기록
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
        
    # 3. 구글 시트에 데이터를 한 번에 추가합니다.
    if rows_to_append:
        data_ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')
        print(f"{len(rows_to_append)}개의 행을 '청구내역 원본' 시트에 성공적으로 추가했습니다.")
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
    """PDF 텍스트에서 청구 데이터를 파싱합니다. (개선된 버전)"""
    # 서비스 구분별로 블록을 나누기 (더 정확한 패턴)
    service_blocks = []
    
    # 다양한 서비스 구분 패턴들
    service_patterns = [
        r'유선전화\s*\(TL\)전국대표번호\(mig\)',
        r'유선전화\s*\(TL\)소호',
        r'유선전화\s*\(TL\)링크기본형\(가상\)',
        r'유선전화\s*\(TL\)링크기본형\(실선\)',
        r'유선전화\s*\(TL\)소호\(가상중계실\)',
        r'유선전화\s*\(TL\)착신과금\(mig\)',
        r'유선전화\s*\(TL\)웹팩스',
        r'유선전화\s*(?!\(TL\))',  # 일반 유선전화
    ]
    
    # 전체 텍스트를 서비스 블록으로 나누기
    split_pattern = '|'.join(service_patterns)
    blocks = re.split(f'({split_pattern})', text)
    
    parsed_data = []
    
    # 블록들을 순회하면서 처리
    for i in range(1, len(blocks), 2):  # 서비스명과 데이터가 번갈아 나타남
        if i + 1 < len(blocks):
            service_type = blocks[i].strip()
            block_content = blocks[i + 1]
            
            # 각 블록에서 개별 전화번호 항목들 추출
            phone_entries = extract_phone_entries_from_block(service_type, block_content)
            parsed_data.extend(phone_entries)
    
    return parsed_data

def extract_phone_entries_from_block(service_type, block_content):
    """서비스 블록 내에서 개별 전화번호 항목들을 추출"""
    entries = []
    
    # 전화번호별로 데이터를 나누기 (합계 기준으로 분리)
    # "합계 XXXXX원" 패턴으로 각 전화번호의 끝을 구분
    phone_sections = re.split(r'합계\s+[\d,]+\s*원', block_content)
    
    for section in phone_sections[:-1]:  # 마지막 섹션은 빈 내용이므로 제외
        entry = extract_single_phone_data(service_type, section)
        if entry:
            entries.append(entry)
    
    return entries

def extract_single_phone_data(service_type, section):
    """개별 전화번호 섹션에서 데이터 추출"""
    # 전화번호 패턴 매칭 (실제 PDF 형태에 맞게 개선)
    phone_number = None
    phone_patterns = [
        # 전국대표번호: **99-2593, **00-1631
        (r'\*\*(\d{2}-\d{4})', 'XXXX-{}'),
        # 070 번호: 070)**03-2573
        (r'070\)\*\*(\d{2}-\d{4})', '070-XX{}'),
        # 02 번호: 02)**35-6493  
        (r'02\)\*\*(\d{2}-\d{4})', '02-XX{}'),
        # 080 번호: 080)**0-7100
        (r'080\)\*\*(\d{1}-\d{4})', '080-XX{}'),
        # 일반 지역번호: 031)**12-3456 등
        (r'(\d{2,3})\)\*\*(\d{2}-\d{4})', '{}-XX{}'),
        # 4자리 번호: 1588)**12-3456 등
        (r'(\d{4})\)\*\*(\d{1,2}-\d{4})', '{}-XX{}'),
    ]
    
    for pattern, format_str in phone_patterns:
        match = re.search(pattern, section)
        if match:
            if '{}' in format_str and len(match.groups()) == 2:
                # 지역번호가 있는 경우
                area_code = match.group(1)
                suffix = match.group(2)
                phone_number = format_str.format(area_code, suffix)
            elif 'XXXX' in format_str:
                # 전국대표번호 등에서 앞부분이 완전 마스킹된 경우
                suffix = match.group(1)
                phone_number = format_str.format(suffix)
            else:
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
