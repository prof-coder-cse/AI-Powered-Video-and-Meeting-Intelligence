from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough , RunnableLambda

load_dotenv()

def get__llm():
    """Initialize and return the language model."""
    return ChatOpenAI(
        model="openrouter/free",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.3
    )

# splitting the text into smaller chunks for better summarization
def split_transcript(transcript: str)->list:
    """Split the transcript into smaller chunks for processing."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=200,
    )
    return text_splitter.split_text(transcript)

def summarize_chunks(transcript : str)-> str:
    """Summarize the transcript using the language model."""
    llm = get__llm()

    map_prompt = ChatPromptTemplate.from_messages(
        [
            ("system" , "Summarize this portion of a meeting transcript in a concise manner, highlighting key points and decisions made. Avoid including filler words or irrelevant details."),
            ("human" , "{text}")
        ]
    )
    map_chain = map_prompt | llm | StrOutputParser()
    chunks = split_transcript(transcript)

    chunk_summaries = [map_chain.invoke({"text": chunk}) for chunk in chunks]
    # adding all summary togethter
    combined = "\n\n".join(chunk_summaries)

    combined_prompt = ChatPromptTemplate.from_messages(
        [
            ("system" , "You are a helpful assistant that summarizes meeting transcripts. Your task is to combine the following summaries into a single, coherent summary, ensuring clarity and conciseness."),
            ("human", "{text}")

        ]
    )

    combined_chain = (RunnablePassthrough() | RunnableLambda(lambda x:{"text": x}) | combined_prompt | llm | StrOutputParser()
                      )
    return combined_chain.invoke(combined)

def generate_title(transcript : str)-> str:
    "Generate a concise title for the meeting transcript."
    llm = get__llm()
    title_prompt = ChatPromptTemplate.from_messages(
        [
            ("system" , "You are a helpful assistant that generates concise and relevant titles for meeting transcripts. Your task is to create a title that accurately reflects the content of the transcript, ensuring it is clear and informative."),
            ("human" , "{text}")
        ]
    )
    title_chain = (RunnablePassthrough() | RunnableLambda(lambda x:{"text": x}) | title_prompt | llm | StrOutputParser())
        
    return title_chain.invoke(transcript[:2000])