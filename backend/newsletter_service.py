


import requests
import logging
import re

logger = logging.getLogger(__name__)

class NewsletterService:
    def __init__(self):
        # Cole seu token aqui
        self.api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI0IiwianRpIjoiYTI5MDNmZDBhNThlNjIzNTcxNjE5ZjIzYTBjOGE2YjRmY2YwODVjOTllZGVjN2E3MWM3OTJlNTY0YzliNjU3ZWZhMmYwMDM2YzY0YjdlODciLCJpYXQiOjE3NTExMzU4MzguNzcwMzg5LCJuYmYiOjE3NTExMzU4MzguNzcwMzkxLCJleHAiOjQ5MDY4MDk0MzguNzY1ODc5LCJzdWIiOiIxMjcwNDc3Iiwic2NvcGVzIjpbXX0.IKIqQeLD431OPprmDOBRzqUfLqD8HXb9LMpw19N-UN-na_yYJG-lUebh06L7rSZ9Asqr6-nTv2cJgO_1qZIm25-WyAsQJJLryj8eaVPw7_dMRfWsmAIA3xVii1VARbCcVD5-A_MNY2u0HmymZMNWvQzvaHs-FUK36lmhurbg2L_LswLtkoy31HXlmrq-FhvL7TnqXCRGoIJu-5Sbpk5cjCntAitVs7A_ZzJBh9LfETfz3gaF8xUcDyF5zAl1gok-YYmH2uQfCbXTZHDhb4W1t2XZaXU9kwRPHExdzTFkIGM-QN35jaB9xbqDoj8PuZJkftuXHJJl637Dtaea8SxG5NfIMaRaTvfjRoGDCgXBrS-an188Iht-q6AGjhcV9pdIGHwha_9vZ4OgW85YhGbhbhxPosmpME1iJMPhRmpFF4hGKZkrjRknfTmHrN9eBFkL35z7kExkqpBv1lbTZBi9FMlMtbtWxXeJjp8tgJ48JkSIIeo-J_3mSPjszROX-Lt2juLslpThBGfhRjp-1b-T2wEywLBfV_tiDj-UjdfP9-BOuUhHE9IQIjt1jMQtnYz8iBob22ExS9HafC1ZInGqO8adjSpTR8kQqDd8Kdz7_PhfaBcwfv8Gd8pUzBp1xxAsOG_IUSBHAXZFSoyfWmqf_VYTjdHD7CqOOq8a1WlY_2M"
        self.group_id = "158477591126214237"
        self.base_url = "https://connect.mailerlite.com/api"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }

    def subscribe_email(self, email: str, name: str = None, source: str = None) -> dict:
        try:
            print(f"📧 Tentando inscrever: {email}")
            
            if not self._validate_email(email):
                return {'success': False, 'error': 'Email inválido'}
            
            subscriber_data = {
                "email": email,
                "groups": [self.group_id],
                "status": "active"
            }
            
            fields = {}
            if name:
                fields["name"] = name
            if source:
                fields["source"] = source
                
            if fields:
                subscriber_data["fields"] = fields
            
            print(f"📡 Enviando para Mailerlite: {subscriber_data}")
            
            url = f"{self.base_url}/subscribers"
            response = requests.post(url, json=subscriber_data, headers=self.headers, timeout=10)
            
            print(f"📋 Resposta Mailerlite: {response.status_code}")
            print(f"📋 Conteúdo: {response.text}")
            
            if response.status_code in [200, 201]:
                return {
                    'success': True,
                    'message': 'Inscrição realizada! Você receberá nossas análises exclusivas.'
                }
            elif response.status_code == 422:
                return {
                    'success': True,
                    'message': 'Você já está inscrito! Continue recebendo nossas análises.'
                }
            else:
                return {'success': False, 'error': 'Erro temporário. Tente novamente.'}
                
        except Exception as e:
            print(f"❌ Erro newsletter: {e}")
            return {'success': False, 'error': 'Erro interno. Tente novamente.'}

    def _validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

newsletter_service = NewsletterService()