from openai import OpenAI
import os
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
from dotenv import load_dotenv

load_dotenv()

# Make sure you set OPENAI_API_KEY in your shell or environment.

def chat_with_gpt(prompt, model="o1-mini"):
    try:
        response = client.chat.completions.create(model=model,
        messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    while True:

        user_input = """"""
        user_input = user_input + input("\nPrompt:")

        answer = chat_with_gpt(user_input)
        print(f"ChatGPT: {answer}")

if __name__ == "__main__":
    main()
