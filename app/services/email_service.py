"""
Email Service
SendGrid email sender for OTP and notifications
"""
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service using SendGrid
    
    Features:
    - Send OTP for password reset
    - Send verification emails
    - Send notifications (future)
    """
    
    def __init__(self):
        """Initialize SendGrid client"""
        self.client = SendGridAPIClient(settings.sendgrid_api_key)
        self.from_email = Email(settings.sendgrid_from_email, settings.sendgrid_from_name)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email via SendGrid
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text fallback (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            to = To(to_email)
            content = Content("text/html", html_content)
            
            mail = Mail(
                from_email=self.from_email,
                to_emails=to,
                subject=subject,
                html_content=content
            )
            
            # Add plain text fallback if provided
            if text_content:
                mail.add_content(Content("text/plain", text_content))
            
            response = self.client.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email to {to_email}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    def send_otp_email(self, to_email: str, otp: str) -> bool:
        """
        Send OTP for password reset
        
        Args:
            to_email: Recipient email
            otp: 6-digit OTP code
            
        Returns:
            True if sent successfully
        """
        subject = "Smart Home - Password Reset OTP"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #4CAF50;">Password Reset Request</h2>
                    <p>You have requested to reset your password for your Smart Home account.</p>
                    <p>Your One-Time Password (OTP) is:</p>
                    <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
                        {otp}
                    </div>
                    <p>This OTP will expire in <strong>10 minutes</strong>.</p>
                    <p>If you did not request this password reset, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="font-size: 12px; color: #999;">
                        This is an automated email from Smart Home IoT system. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        You have requested to reset your password for your Smart Home account.
        
        Your One-Time Password (OTP) is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you did not request this password reset, please ignore this email.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_verification_email(self, to_email: str, otp: str) -> bool:
        """
        Send email verification OTP
        
        Args:
            to_email: Recipient email
            otp: 6-digit verification OTP
            
        Returns:
            True if sent successfully
        """
        subject = "Smart Home - Verify Your Email"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #4CAF50;">Welcome to Smart Home!</h2>
                    <p>Thank you for registering. Please verify your email address to activate your account.</p>
                    <p>Your verification code is:</p>
                    <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
                        {otp}
                    </div>
                    <p>This code will expire in <strong>10 minutes</strong>.</p>
                    <p>If you did not create this account, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="font-size: 12px; color: #999;">
                        This is an automated email from Smart Home IoT system. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Smart Home!
        
        Thank you for registering. Please verify your email address to activate your account.
        
        Your verification code is: {otp}
        
        This code will expire in 10 minutes.
        
        If you did not create this account, please ignore this email.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_welcome_email(self, to_email: str, full_name: str) -> bool:
        """
        Send welcome email after registration
        
        Args:
            to_email: Recipient email
            full_name: User's full name
            
        Returns:
            True if sent successfully
        """
        subject = "Welcome to Smart Home!"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #4CAF50;">Welcome, {full_name}!</h2>
                    <p>Your Smart Home account has been created successfully.</p>
                    <p>You can now:</p>
                    <ul>
                        <li>Create your first home</li>
                        <li>Pair IoT boards</li>
                        <li>Control your devices</li>
                        <li>Set up timers and automations</li>
                    </ul>
                    <p>Get started by logging in to your account.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="font-size: 12px; color: #999;">
                        This is an automated email from Smart Home IoT system. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)


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