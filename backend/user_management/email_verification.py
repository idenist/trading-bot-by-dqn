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

    def generate_token(self, data: dict) -> str:
        """
        가입정보를 포함하는 만료 시간 설정된 토큰을 생성합니다.
        """
        # 토큰에 포함시킬 데이터를 딕셔너리로 구성
        data['iat'] = int(time.time()) # 'issued at' (발급 시간)
        return self.serializer.dumps(data)

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
        
def get_mail_template(verification_link: str) -> str:
    """이메일 본문 HTML 템플릿을 반환합니다."""
    return f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>이메일 인증</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, 'Nanum Gothic', sans-serif;">

  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f4f4; padding: 20px 0;">
    <tr>
      <td align="center">
        
        <table width="600" border="0" cellspacing="0" cellpadding="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
          
          <tr>
            <td style="padding: 40px 30px 20px 30px; text-align: center; border-bottom: 1px solid #eeeeee;">
              <h1 style="margin: 0; font-size: 24px; color: #333333; font-weight: bold;">
                TRADING_BOT_BY_DQN
              </h1>
            </td>
          </tr>

          <tr>
            <td style="padding: 40px 30px 30px 30px; font-size: 16px; line-height: 1.6; color: #555555;">
              <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #333333;">이메일 주소를 인증해 주세요</h2>
              
              <p style="margin: 0 0 20px 0;">
                안녕하세요!
              </p>
              
              <p style="margin: 0 0 30px 0;">
                TRADING_BOT_BY_DQN 의 계정 생성을 완료하려면 아래 버튼을 클릭하여 이메일 주소를 인증해 주세요.
              </p>

              <table border="0" cellspacing="0" cellpadding="0" width="100%">
                <tr>
                  <td align="center">
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" style="border-radius: 5px; background-color: #007bff;">
                          <a href="{verification_link}" target="_blank" style="display: inline-block; padding: 12px 25px; font-size: 16px; font-weight: bold; color: #ffffff; text-decoration: none; border-radius: 5px;">
                            이메일 인증하기
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              
              <p style="margin: 30px 0 20px 0; font-size: 14px; color: #777777;">
                버튼이 작동하지 않는 경우, 아래 링크를 복사하여 브라우저 주소창에 붙여넣으세요:
              </p>
              <p style="margin: 0; word-break: break-all;">
                <a href="{ verification_link }" target="_blank" style="color: #007bff; text-decoration: underline;">
                  { verification_link }
                </a>
              </p>

              <p style="margin: 30px 0 0 0; font-size: 14px; color: #777777;">
                이 인증 링크는 10분 동안 유효합니다.
              </p>

            </td>
          </tr>

          <tr>
            <td style="padding: 30px 30px 30px 30px; border-top: 1px solid #eeeeee; text-align: center; font-size: 12px; color: #999999;">
              <p style="margin: 0 0 10px 0;">
                본인이 요청하지 않은 메일이라면 이 메일을 무시하거나 삭제해 주세요.
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>
    """
    
def get_verification_state_page(is_success: bool, msg: str = "알 수 없는 오류.") -> str:
    """이메일 인증 성공/실패 페이지 HTML 템플릿을 반환합니다."""
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:8081")
    title = "인증 성공" if is_success else "인증 실패"
    icon_color = "#28a745" if is_success else "#dc3545"
    content = "이메일 인증이 성공적으로 완료되었습니다." if is_success else msg
    link = f"""<a href="{frontend_base_url}/login/" class="button">로그인 페이지로 이동</a>""" if is_success else f"""<a href="{frontend_base_url}/register/" class="button">회원가입 페이지로 이동</a>"""
    return f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      font-family: Arial, 'Nanum Gothic', sans-serif;
      background-color: #f4f4f4;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }}
    .container {{
      background-color: #ffffff;
      border-radius: 8px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
      padding: 40px 30px;
      text-align: center;
      width: 90%;
      max-width: 450px;
    }}
    .icon {{
      font-size: 50px;
      color: {icon_color}
    }}
    h1 {{
      color: #333;
      margin-top: 20px;
      margin-bottom: 10px;
    }}
    p {{
      color: #555;
      font-size: 16px;
      line-height: 1.6;
    }}
    .button {{
      display: inline-block;
      margin-top: 25px;
      padding: 12px 25px;
      background-color: #007bff;
      color: #ffffff;
      text-decoration: none;
      font-weight: bold;
      border-radius: 5px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">✓</div>
    <h1>{title}</h1>
    <p>
      {content}
    </p>
    {link}
  </div>
</body>
</html>
    """
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
        html = get_mail_template(verification_link)
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