"""
Email Service - Resend Integration
Send emails for Smart Home IoT Backend
"""
import logging
import resend
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service using Resend"""
    
    def __init__(self):
        """Initialize email service"""
        resend.api_key = settings.resend_api_key
        self.from_email = settings.email_from
        self.from_name = settings.email_from_name
        logger.info(f"Email service initialized (from: {self.from_email})")
    
    def send_otp_email(self, to_email: str, otp: str) -> bool:
        """
        Send OTP email for password reset
        
        Args:
            to_email: Recipient email
            otp: 6-digit OTP code
            
        Returns:
            True if sent successfully
        """
        try:
            resend.api_key = settings.resend_api_key
        
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>
                Mã xác thực của bạn là:
                <span>{otp}</span>
                Hết hạn sau 10ph!
            </body>
            </html>
            """
        
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "Smart Home - Mã OTP Đặt Lại Mật Khẩu",
                "html": html_content,
            }
        
            email = resend.Emails.send(params)
            logger.info(f"OTP email sent to {to_email} (ID: {email['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {str(e)}")
            return False
    
    def send_verification_email(self, to_email: str, otp: str) -> bool:
        """
        Send email verification OTP
        
        Args:
            to_email: Recipient email
            otp: 6-digit verification code
            
        Returns:
            True if sent successfully
        """
        try:
            resend.api_key = settings.resend_api_key
        
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>
                Mã xác thực của bạn là:
                <span>{otp}</span>
                <br>
                Hết hạn sau 10ph!
            </body>
            </html>
            """
        
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "Smart Home - Xác Thực Email",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            logger.info(f"Verification email sent to {to_email} (ID: {email['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {str(e)}")
            return False
    
    def send_welcome_email(self, to_email: str, full_name: str) -> bool:
        """
        Send welcome email after registration
        
        Args:
            to_email: Recipient email
            full_name: User's full name
            
        Returns:
            True if sent successfully
        """
        try:
            resend.api_key = settings.resend_api_key
        
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body>
                Chào bạn, tôi đẹp bạn cũng thế!
            </body>
            </html>
            """
        
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "Chào Mừng Đến Với Smart Home IoT!",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            logger.info(f"Welcome email sent to {to_email} (ID: {email['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to_email}: {str(e)}")
            return False


# Global email service instance
email_service = EmailService()


# Helper functions for easy import
def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP email"""
    return email_service.send_otp_email(to_email, otp)


def send_verification_email(to_email: str, otp: str) -> bool:
    """Send verification OTP email"""
    return email_service.send_verification_email(to_email, otp)


def send_welcome_email(to_email: str, full_name: str) -> bool:
    """Send welcome email"""
    return email_service.send_welcome_email(to_email, full_name)