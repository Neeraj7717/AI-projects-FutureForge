from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from langchain_community.llms import HuggingFaceHub
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
# from Config import Tokens

class QuestionAnswerModel:
    def __init__(self):
        """
        Initialize the QuestionAnswerModel.

        Args:
            repo_id (str): The Hugging Face model repository ID.
            api_token (str): Hugging Face API token for authentication.
            temperature (float): Temperature parameter for controlling the randomness of model responses.
            max_length (int): Maximum length of the generated response.
        """
        # self.tokens = Tokens()
        self.repo_id = "google/flan-t5-xxl"
        self.api_token = "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"
        self.temperature = 0.5
        self.max_length = 64

    def generate_answer(self, context, question):
        """
        Generate a response to a given question based on the provided context.

        Args:
            context (str): The context in which the question is asked.
            question (str): The question to be answered.

        Returns:
            str: The generated response.
        """
        # Define the template for the prompt
        template = """### Instruction: By using the below context, answer the question.

### Context: {context}
### Question: {question}
### Response: """

        # Create a PromptTemplate
        prompt = PromptTemplate(template=template, input_variables=["context", "question"])

        # Create an instance of HuggingFaceHub with the specified model and parameters
        llm = HuggingFaceHub(
            repo_id=self.repo_id,
            model_kwargs={"temperature": self.temperature, "max_length": self.max_length},
            huggingfacehub_api_token=self.api_token
        )

        # Create an LLMChain with the prompt and HuggingFaceHub instance
        llm_chain = LLMChain(prompt=prompt, llm=llm)

        # Generate the response
        answer = llm_chain.run({'context': context, 'question': question})

        return {"answer": answer}

