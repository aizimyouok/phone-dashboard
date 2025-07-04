# 📞 전화요금 대시보드

SK브로드밴드 청구서 PDF를 자동으로 파싱하고 구글 시트와 연동하여 웹 대시보드로 조회할 수 있는 시스템입니다.

## 🚀 두 가지 배포 방법

### 🌟 방법 1: Google Apps Script (추천 - 영구 무료!)

- ✅ **완전 무료** (데이터 계속 쌓여도 무료)
- ✅ **어디서든 접속** 가능한 웹 URL
- ✅ **모바일 지원** (스마트폰에서도 완벽 작동)
- ✅ **구글 계정으로 자동 인증**
- ✅ **HTTPS 자동 제공**

👉 **[Apps Script 배포 가이드](apps-script/README.md)**

### 🛠️ 방법 2: Flask 로컬 실행

- ✅ **완전한 PDF 업로드** 기능
- ✅ **개발자 친화적**
- ❌ 로컬에서만 실행 가능

👉 **아래 설치 가이드 참조**

## ✨ 주요 기능

### 📁 PDF 자동 처리
- 청구서 PDF 파일 업로드
- 전화번호별 요금 데이터 자동 추출
- 구글 시트 자동 업데이트

### 📊 실시간 대시보드
- KPI 카드로 한눈에 보는 요금 현황
- 지점별 요금 상위 차트
- 문제 회선 목록 (기본료만 발생)

### 🔍 강력한 필터링
- **지점별 필터**: 특정 지점의 데이터만 조회
- **월별 필터**: 특정 월의 요금 현황 분석
- **회선유형 필터**: 
  - 기본료만 발생하는 회선
  - 부가서비스 사용 회선

### 📞 검색 기능
- 전화번호로 빠른 검색
- 해당 번호의 사용 내역 조회

## 🚀 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/aizimyouok/phone-dashboard.git
cd phone-dashboard
```

### 2. 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 3. 구글 서비스 계정 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API, Google Drive API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. 키 파일을 프로젝트 폴더에 저장
5. `app.py`에서 `KEY_FILE_PATH` 수정

### 4. 구글 시트 공유
- 구글 시트에 서비스 계정 이메일 주소를 편집자로 공유
- 시트 이름을 `app.py`의 `SPREADSHEET_NAME`과 일치시키기

### 5. 서버 실행
```bash
python app.py
```

브라우저에서 http://localhost:5000 접속

## 📋 구글 시트 구조

### 전화번호 마스터 시트
| 컬럼명 | 설명 |
|--------|------|
| 전화번호 | 070-1234-5678 형식 |
| 지점명 | 해당 번호가 속한 지점 |

### 청구내역 원본 시트
| 컬럼명 | 설명 |
|--------|------|
| 청구월 | YYYY-MM 형식 |
| 지점명 | 마스터와 연동된 지점명 |
| 전화번호 | 전체 전화번호 |
| 기본료 | 인터넷전화 기본료 |
| 시내통화료 | 시내 통화 요금 |
| 이동통화료 | 이동전화 통화 요금 |
| 070통화료 | 070 통화 요금 |
| 정보통화료 | 정보이용료 |
| 부가서비스료 | 부가서비스 이용료 |
| 사용요금계 | 사용요금 합계 |
| 할인액 | 할인 금액 |
| 부가세 | 부가가치세 |
| 최종합계 | 최종 청구 금액 |

## 🔧 기술 스택

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: Google Sheets
- **PDF Processing**: pypdf
- **Charts**: Chart.js
- **Authentication**: Google Service Account

## 📸 스크린샷

### 메인 대시보드
- KPI 카드와 차트로 한눈에 보는 현황

### 필터링 기능
- 다양한 조건으로 데이터 필터링

### PDF 업로드
- 드래그 앤 드롭으로 간편한 PDF 업로드

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다.

## 📞 문의

질문이나 제안사항이 있으시면 이슈를 등록해 주세요.
