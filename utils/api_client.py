import requests

class APIClient:
    def __init__(self, api_url):
        self.api_url = api_url
    
    def call_api(self, data):
        response = requests.post(self.api_url, json=data)
        if response.status_code == 200:
            return response.text
        else:
            return f"Error: {response.status_code}"

# # Example usage
# api_url = 'http://example.com/api/endpoint'
# api_client = APIClient(api_url)

# data = {
#     "file": "https://campaigntool.s3.ap-south-1.amazonaws.com/edusecase/1.jpeg",
#     "question": "Is the Chemical Equation shown in the image correct or not? Give me one word answer, Yes or No"
# }

# response_string = api_client.call_api(data)
# print("Response:", response_string)