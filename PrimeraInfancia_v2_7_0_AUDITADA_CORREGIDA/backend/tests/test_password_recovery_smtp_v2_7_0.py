from pathlib import Path
import sys
from unittest.mock import patch
from flask import Flask
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from modules.seguridad.services import send_password_reset_email

class FakeSMTP:
    instance=None
    def __init__(self,host,port,timeout=None,**kwargs):self.host=host;self.port=port;self.timeout=timeout;self.logged=None;self.message=None;FakeSMTP.instance=self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def ehlo(self):pass
    def starttls(self,context=None):self.tls=True
    def login(self,user,password):self.logged=(user,password)
    def send_message(self,message):self.message=message

app=Flask(__name__);app.config.update(SMTP_HOST='smtp.gmail.com',SMTP_PORT=587,SMTP_USERNAME='cuenta@gmail.com',SMTP_PASSWORD='app-password-test',SMTP_USE_TLS=True,SMTP_USE_SSL=False,SMTP_TIMEOUT_SECONDS=15,PASSWORD_RESET_FROM_EMAIL='cuenta@gmail.com')
with app.app_context(),patch('modules.seguridad.services.smtplib.SMTP',FakeSMTP):
    assert send_password_reset_email('destino@example.com','http://127.0.0.1:5000/#restablecer?reset_token=token-prueba')
    smtp=FakeSMTP.instance
    assert smtp.logged==('cuenta@gmail.com','app-password-test')
    assert smtp.message['To']=='destino@example.com'
    assert 'token-prueba' in smtp.message.as_string()

source=(ROOT/'backend/modules/seguridad/services.py').read_text(encoding='utf-8')
assert 'resend.com' not in source.lower() and 'RESEND_API_KEY' not in source
print('Recuperación Gmail SMTP 2.7.0: PASS')
