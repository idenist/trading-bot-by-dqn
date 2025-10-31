from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import time
import os
from dotenv import load_dotenv

class EmailVerifier:
    
    def __init__(self, secret_key: str, default_timeout_seconds: int = 600):
        """
        :param secret_key: 토큰 서명에 사용할 비밀 키 (절대 노출 금지)
        :param default_timeout_seconds: 토큰의 기본 만료 시간 (기본값: 30분)
        """
        if not secret_key:
            raise ValueError("Secret key는 필수입니다.")
            
        self.secret_key = secret_key
        self.default_timeout_seconds = default_timeout_seconds
        # 'salt'는 토큰의 용도를 구분하기 위해 사용됩니다. (예: 'email-verify')
        self.serializer = URLSafeTimedSerializer(self.secret_key, salt='email-verification')

    def generate_token(self, email: str) -> str:
        """
        이메일과 사용자 ID를 포함하는 만료 시간 설정된 토큰을 생성합니다.
        """
        # 토큰에 포함시킬 데이터를 딕셔너리로 구성
        data_to_sign = {
            'email': email,
            'iat': int(time.time()) # 'issued at' (발급 시간)
        }
        return self.serializer.dumps(data_to_sign)

    def verify_token(self, token: str) -> dict | None:
        """
        제공된 토큰을 검증하고, 유효하면 포함된 데이터를 반환합니다.
        만료되었거나 유효하지 않으면 None을 반환합니다.
        """
        try:
            # max_age를 설정하여 토큰의 유효 기간을 검사합니다.
            data = self.serializer.loads(token, max_age=self.default_timeout_seconds)
            
            # 토큰에서 데이터를 성공적으로 로드하면 (email, user_id 등) 반환
            return data
        
        except SignatureExpired:
            # 토큰이 만료됨
            print("토큰이 만료되었습니다.")
            return None
        except BadTimeSignature:
            # 토큰 서명이 유효하지 않음 (조작되었거나 키가 다름)
            print("토큰 서명이 유효하지 않습니다.")
            return None
        except Exception as e:
            # 기타 예외
            print(f"토큰 검증 오류: {e}")
            return None
        
    def get_email_from_token(self, token: str) -> str | None:
        """
        토큰에서 이메일을 추출합니다. 토큰이 유효하지 않으면 None을 반환합니다.
        """
        data = self.verify_token(token)
        if data and 'email' in data:
            return data['email']
        return None
        
    
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Gmail 앱 비밀번호 또는 SMTP 설정
load_dotenv()
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

async def send_verification_email(recipient_email: str, verification_link: str):
    """지정된 이메일로 인증 링크를 발송합니다."""
    
    try:
        # 이메일 메시지 구성
        message = MIMEMultipart("alternative")
        message["Subject"] = "이메일 인증을 완료해주세요."
        message["From"] = SENDER_EMAIL
        message["To"] = recipient_email

        # 이메일 본문 (HTML)
        html = f"""
        <html>
        <body>
            <p>안녕하세요!</p>
            <p>아래 링크를 클릭하여 이메일 인증을 완료해주세요 (링크는 10분간 유효합니다):</p>
            <a href="{verification_link}">{verification_link}</a>
            <p>감사합니다.</p>
        </body>
        </html>
        """
        message.attach(MIMEText(html, "html"))

        # SMTP 서버 연결 및 메일 발송
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()  # TLS 보안 연결
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, message.as_string())
        
        print(f"인증 메일 발송 성공: {recipient_email}")
        return True
        
    except Exception as e:
        print(f"메일 발송 실패: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    # 테스트용 코드
    load_dotenv()
    SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    verifier = EmailVerifier(SECRET_KEY)

    test_email = input("test email: ")
    asyncio.run(send_verification_email(test_email, verifier.generate_token(test_email, "testuser")))