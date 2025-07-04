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
    
    # 1. '전화번호 마스터'에서 모든 데이터를 가져와서 {전체 전화번호: 지점명} 딕셔너리로 만듭니다.
    master_records = master_ws.get_all_records()
    # 마스터 시트의 전체 전화번호와 지점명을 모두 불러옵니다.
    master_phone_list = {str(record['전화번호']).strip(): record['지점명'] for record in master_records}
    print("'전화번호 마스터' 정보를 메모리에 로드했습니다.")

    # 2. '청구내역 원본'에 기록할 데이터를 만듭니다.
    rows_to_append = []
    column_order = [
        '청구월', '지점명', '전화번호', '기본료', '시내통화료', '이동통화료', 
        '070통화료', '정보통화료', '부가서비스료', '사용요금계', '할인액', '부가세', '최종합계'
    ]

    for data in invoice_data:
        pdf_phone_number = data['전화번호'] # 예: "070-XX95-3210"
        pdf_suffix = pdf_phone_number[-7:] # 뒷자리 7글자 "95-3210"을 추출합니다.

        branch_name = '미배정'
        full_phone_number = pdf_phone_number # 기본값은 XX가 포함된 번호

        # 마스터의 전체 전화번호 목록을 순회하며 뒷자리를 비교합니다.
        for master_phone, master_branch in master_phone_list.items():
            if master_phone.endswith(pdf_suffix):
                branch_name = master_branch # 지점명을 찾습니다.
                full_phone_number = master_phone # 실제 전체 번호로 교체합니다.
                break # 일치하는 번호를 찾으면 반복을 중단합니다.

        # column_order 순서에 맞게 한 줄의 데이터를 리스트로 만듭니다.
        row = [
            billing_month,
            branch_name,
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
        
    # 3. 구글 시트에 데이터를 한 번에 추가합니다.
    if rows_to_append:
        data_ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')
        print(f"{len(rows_to_append)}개의 행을 '청구내역 원본' 시트에 성공적으로 추가했습니다.")
    else:
        print("시트에 추가할 데이터가 없습니다.")
        
    print("--- 구글 시트 업데이트 완료 ---")


# --- 데이터 파싱 및 유틸리티 함수 (이전과 거의 동일) ---
def get_billing_month(text):
    """텍스트에서 'YYYY년 MM월'을 찾아 'YYYY-MM' 형식으로 반환합니다."""
    match = re.search(r'(\d{4})년\s*(\d{2})월', text)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return "날짜모름"

def parse_invoice_data(text):
    blocks = re.split(r'유선전화', text)
    parsed_data = []
    for block in blocks[1:]:
        phone_match = re.search(r'070\)\*\*(\d{2}-\d{4})', block)
        if not phone_match:
            continue
        phone_number = f"070-XX{phone_match.group(1)}"
        
        def find_amount(pattern):
            match = re.search(pattern, block)
            return int(match.group(1).replace(',', '')) if match else 0

        data = {
            '전화번호': phone_number,
            '기본료': find_amount(r'인터넷전화기본료\s+([\d,]+)'),
            '시내통화료': find_amount(r'시내통화료\s+([\d,]+)'),
            '이동통화료': find_amount(r'이동통화료\s+([\d,]+)'),
            '070통화료': find_amount(r'인터넷전화통화료\(070\)\s+([\d,]+)'),
            '정보통화료': find_amount(r'정보통화료\s+([\d,]+)'),
            '부가서비스료': find_amount(r'부가서비스이용료\s+([\d,]+)'),
            '사용요금계': find_amount(r'사용요금 계\s+([\d,]+)'),
            '할인액': find_amount(r'할인\s+-([\d,]+)'),
            '부가세': find_amount(r'부가가치세\(세금\)\*\s+([\d,]+)'),
            '최종합계': find_amount(r'합계\s+([\d,]+)')
        }
        parsed_data.append(data)
    return parsed_data

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
                update_spreadsheet(master_worksheet, data_worksheet, invoice_data, billing_month)
                print("\n모든 작업이 성공적으로 완료되었습니다!")
            else:
                print("PDF에서 유효한 요금 데이터를 찾지 못했습니다.")