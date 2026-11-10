import os
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def get_llm(temperature=0.2):
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    

    if not api_key:
        try:
            api_key = st.secrets["OPENROUTER_API_KEY"]
        except (KeyError, FileNotFoundError):
            api_key = None
    print("LLM RUNTIME KEY FOUND:", bool(api_key))
    print("LLM RUNTIME KEY LENGTH:", len(api_key) if api_key else 0)

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing!")

    return ChatOpenAI(
        model="openrouter/free",
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature
    )