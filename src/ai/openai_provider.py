import os

from dotenv import load_dotenv
from openai import OpenAI

from ai.base import AIProvider


load_dotenv()


class OpenAIProvider(AIProvider):

    def __init__(self):

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:

            raise ValueError(
                "OPENAI_API_KEY was not found in .env"
            )

        self.ai_model = os.getenv(
            "AI_MODEL",
            "gpt-5-mini"
        )

        self.search_model = os.getenv(
            "SEARCH_MODEL",
            self.ai_model
        )

        self.client = OpenAI(
            api_key=api_key
        )


    # ======================================================
    # Normal AI analysis
    # ======================================================

    def analyze(self, prompt):

        response = self.client.responses.create(
            model=self.ai_model,
            input=prompt
        )

        return response.output_text


    # ======================================================
    # Web search
    # ======================================================

    def search_web(self, prompt):

        response = self.client.responses.create(
            model=self.search_model,

            tools=[
                {
                    "type": "web_search"
                }
            ],

            input=prompt
        )

        return response.output_text